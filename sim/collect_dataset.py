"""Genera el dataset de imitación de la Fase 4: partidas 100% heurísticas
(self-play de BotAI) donde cada decisión "qué carta jugar" se registra
como una fila por cada CARTA (nombre único, no índice) candidata legal,
con label=1 para la que la heurística realmente eligió.

Escribe en shards comprimidos (.npz) en vez de un CSV único — con 100k
partidas el dataset son decenas de millones de filas (~9GB en float32),
demasiado para tenerlo todo en memoria a la vez en una máquina normal.
Usa `load_dataset.py` para cargar una muestra manejable al entrenar.

Uso:
    python sim/collect_dataset.py -n 100000 -o dataset_shards
"""
import argparse
import builtins
import contextlib
import json
import os
import sys
import time

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bang_game import info_extract, create_players, Juego  # noqa: E402
from bot_ai import BotAI  # noqa: E402
from sim_io import SimIO  # noqa: E402
from mcts_bot import MCTSBotAI  # noqa: E402
from features import features_estado, fila_completa, nombre_de_opcion, NOMBRES_FEATURES  # noqa: E402

CARTAS_CSV = os.path.join(BASE_DIR, "cartas.csv")
PERSONAJES_TXT = os.path.join(BASE_DIR, "personajes.txt")
ROLES_TXT = os.path.join(BASE_DIR, "roles.txt")

FILAS_POR_SHARD = 200_000


@contextlib.contextmanager
def _silenciar_print():
    orig = builtins.print
    builtins.print = lambda *a, **k: None
    try:
        yield
    finally:
        builtins.print = orig


class CollectorIO(SimIO):
    """SimIO que además registra cada decisión de "qué carta jugar" en
    `writer` (una fila por nombre único de carta candidata + FIN/PODER)."""

    def __init__(self, bots, writer, jugadores_a_grabar=None, max_pasos=None):
        super().__init__(bots, max_pasos=max_pasos)
        self._writer = writer
        self._jugadores_a_grabar = jugadores_a_grabar  # None = todos

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        mano = [
            {"nombre": c.nombre, "tipo": c.tipo, "idClase": c.idClase, "indice": i}
            for i, c in enumerate(jugador.cartasMano)
        ]
        resp = super().elegir_carta(jugador, text, opciones, permitir_fin, permitir_poder)
        if self._jugadores_a_grabar is None or jugador.idJugador in self._jugadores_a_grabar:
            self._registrar(jugador, mano, opciones, resp, permitir_fin, permitir_poder)
        return resp

    def _registrar(self, jugador, mano, opciones, resp, permitir_fin, permitir_poder):
        opciones_todas = list(opciones)
        if permitir_fin:
            opciones_todas.append("FIN")
        if permitir_poder:
            opciones_todas.append("PODER")
        if len(opciones_todas) <= 1:
            return

        nombre_elegido = nombre_de_opcion(resp, mano)
        nombres_candidatos = set()
        for op in opciones_todas:
            n = nombre_de_opcion(op, mano)
            if n is not None:
                nombres_candidatos.add(n)
        if nombre_elegido is None or nombre_elegido not in nombres_candidatos:
            return

        estado_feats = features_estado({"mano": mano}, jugador, self.juego)
        for nombre in nombres_candidatos:
            self._writer(fila_completa(estado_feats, nombre, 1 if nombre == nombre_elegido else 0))


class EscritorShards:
    """Acumula filas (dicts) en un buffer y las vuelca a shards .npz
    comprimidos cuando el buffer llega a FILAS_POR_SHARD, para no tener
    nunca en memoria más que un shard a la vez."""

    def __init__(self, carpeta, columnas):
        self.carpeta = carpeta
        self.columnas = columnas
        os.makedirs(carpeta, exist_ok=True)
        self._buffer = []
        self._shard_idx = 0
        self.total_filas = 0

    def escribir_fila(self, fila):
        self._buffer.append([fila.get(c, 0.0) for c in self.columnas])
        self.total_filas += 1
        if len(self._buffer) >= FILAS_POR_SHARD:
            self._flush()

    def _flush(self):
        if not self._buffer:
            return
        arr = np.asarray(self._buffer, dtype=np.float32)
        X, y = arr[:, :-1], arr[:, -1]
        path = os.path.join(self.carpeta, f"shard_{self._shard_idx:05d}.npz")
        np.savez_compressed(path, X=X, y=y)
        self._shard_idx += 1
        self._buffer = []

    def cerrar(self):
        self._flush()
        manifest = {
            "columnas": self.columnas[:-1],  # sin "label"
            "n_shards": self._shard_idx,
            "total_filas": self.total_filas,
        }
        with open(os.path.join(self.carpeta, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)


def generar(n_partidas, num_players, escribir_fila, experto="heuristico",
            presupuesto_mcts=0.03, max_pasos=3000, progreso_cada=2000):
    partidas_ok = 0
    t0 = time.perf_counter()
    for i in range(n_partidas):
        baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
        nombres = [f"Bot{j}" for j in range(num_players)]
        if experto == "mcts":
            bots = {0: MCTSBotAI(0, presupuesto_s=presupuesto_mcts)}
            for j in range(1, num_players):
                bots[j] = BotAI(j)
            jugadores_a_grabar = {0}
        else:
            bots = {j: BotAI(j) for j in range(num_players)}
            jugadores_a_grabar = None
        io = CollectorIO(bots, writer=escribir_fila, jugadores_a_grabar=jugadores_a_grabar, max_pasos=max_pasos)
        jugadores = create_players(num_players, nombres, personajes, roles, io=io)
        juego = Juego(jugadores, baraja, io=io)
        io.set_game(juego)
        with _silenciar_print():
            try:
                juego.partida()
                partidas_ok += 1
            except Exception:
                pass
        if (i + 1) % progreso_cada == 0:
            elapsed = time.perf_counter() - t0
            print(f"  {i+1}/{n_partidas} partidas ({partidas_ok} ok) | "
                  f"{elapsed:.1f}s ({(i+1)/elapsed:.1f} partidas/s)", flush=True)
    return partidas_ok


def main():
    parser = argparse.ArgumentParser(description="Genera el dataset de imitación (Fase 4) en shards .npz")
    parser.add_argument("-n", "--partidas", type=int, default=1000)
    parser.add_argument("-p", "--players", type=int, default=4, choices=[4, 5, 6, 7])
    parser.add_argument("-o", "--out", type=str, default="dataset_shards")
    parser.add_argument("--experto", choices=["heuristico", "mcts"], default="heuristico")
    parser.add_argument("--presupuesto-mcts", type=float, default=0.03)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

    escritor = EscritorShards(args.out, NOMBRES_FEATURES + ["label"])
    t0 = time.perf_counter()
    partidas_ok = generar(args.partidas, args.players, escritor.escribir_fila,
                           experto=args.experto, presupuesto_mcts=args.presupuesto_mcts)
    escritor.cerrar()

    print(f"\nTerminado ({args.experto}): {partidas_ok}/{args.partidas} partidas ok -> "
          f"{escritor.total_filas} filas en {escritor._shard_idx} shards bajo {args.out}/ "
          f"({time.perf_counter()-t0:.1f}s)")


if __name__ == "__main__":
    main()
