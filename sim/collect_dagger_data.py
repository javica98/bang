"""DAgger (Dataset Aggregation) para la Fase 4: en vez de solo partidas de
autojuego del experto, se dejan jugar partidas con la POLÍTICA YA
ENTRENADA (DLBotAI) y en cada uno de los estados que ella visita se le
pregunta al experto (BotAI heurístico) qué habría hecho — esa etiqueta es
la que se guarda, no la elección de la política. Así se corrigen los
estados donde la política se equivoca y que el autojuego puro del experto
nunca visitaría (el problema clásico de "distribution shift" del
aprendizaje por imitación puro).

DLBotAI ya mantiene una instancia de BotAI interna con las creencias
sincronizadas (la usa para delegar lo que no es "qué carta jugar"), así
que preguntarle "qué harías tú aquí" es gratis, no hace falta duplicar
lógica de creencias.

Uso:
    python sim/collect_dagger_data.py -n 2000 -o dagger_data.npz --modelo-dl modelo_torch.pt
"""
import argparse
import builtins
import contextlib
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
from dl_bot import DLBotAI  # noqa: E402
from features import features_estado, fila_completa, nombre_de_opcion, NOMBRES_FEATURES  # noqa: E402

CARTAS_CSV = os.path.join(BASE_DIR, "cartas.csv")
PERSONAJES_TXT = os.path.join(BASE_DIR, "personajes.txt")
ROLES_TXT = os.path.join(BASE_DIR, "roles.txt")


@contextlib.contextmanager
def _silenciar_print():
    orig = builtins.print
    builtins.print = lambda *a, **k: None
    try:
        yield
    finally:
        builtins.print = orig


class DLBotAIConEtiquetaExperta(DLBotAI):
    """Juega con SU PROPIA política (para visitar los estados que ella
    realmente visita, aciertos y errores incluidos), pero en cada decisión
    de carta registra la etiqueta del EXPERTO (la heurística interna, que
    ya tiene las creencias al día) para ese mismo estado — es la esencia
    de DAgger: corregir los estados de la política, no repetir los del
    autojuego del experto."""

    def __init__(self, bot_id, writer, **kwargs):
        super().__init__(bot_id, **kwargs)
        self._writer = writer

    def decidir(self, pregunta, jugador, juego):
        if juego is not None:
            self._heuristico._inicializar(juego)
        if pregunta.get("tipo") == "elegir_carta":
            self._grabar_etiqueta_experta(pregunta, jugador, juego)
            return self._decidir_carta_dl(pregunta, jugador, juego)
        return self._heuristico.decidir(pregunta, jugador, juego)

    def _grabar_etiqueta_experta(self, pregunta, jugador, juego):
        mano = pregunta.get("mano", [])
        opciones_todas = list(pregunta.get("opciones", []))
        if pregunta.get("permitir_fin", True):
            opciones_todas.append("FIN")
        if pregunta.get("permitir_poder", False):
            opciones_todas.append("PODER")
        if len(opciones_todas) <= 1:
            return

        nombres_candidatos = set()
        for op in opciones_todas:
            n = nombre_de_opcion(op, mano)
            if n is not None:
                nombres_candidatos.add(n)
        if not nombres_candidatos:
            return

        respuesta_experta = self._heuristico._elegir_carta(pregunta, jugador, juego)
        nombre_experto = nombre_de_opcion(respuesta_experta, mano)
        if nombre_experto is None or nombre_experto not in nombres_candidatos:
            return

        estado_feats = features_estado({"mano": mano}, jugador, juego)
        for nombre in nombres_candidatos:
            self._writer(fila_completa(estado_feats, nombre, 1 if nombre == nombre_experto else 0))


def generar(n_partidas, num_players, escribir, modelo_dl_path, backend, max_pasos=2000, progreso_cada=200):
    partidas_ok = 0
    t0 = time.perf_counter()
    for i in range(n_partidas):
        baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
        nombres = [f"Bot{j}" for j in range(num_players)]
        bots = {0: DLBotAIConEtiquetaExperta(0, escribir, backend=backend, modelo_path=modelo_dl_path)}
        for j in range(1, num_players):
            bots[j] = BotAI(j)
        io = SimIO(bots, max_pasos=max_pasos)
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
                  f"{elapsed:.1f}s ({(i+1)/elapsed:.2f} partidas/s)", flush=True)
    return partidas_ok


def main():
    parser = argparse.ArgumentParser(description="Genera datos DAgger (Fase 4)")
    parser.add_argument("-n", "--partidas", type=int, default=2000)
    parser.add_argument("-p", "--players", type=int, default=4, choices=[4, 5, 6, 7])
    parser.add_argument("-o", "--out", type=str, default="dagger_data.npz")
    parser.add_argument("--modelo-dl", required=True, help="Modelo DL ya entrenado a corregir")
    parser.add_argument("--backend", choices=["sklearn", "torch", "xgboost"], default="torch")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    filas = []

    def escribir(fila):
        filas.append([fila.get(c, 0.0) for c in NOMBRES_FEATURES + ["label"]])

    t0 = time.perf_counter()
    partidas_ok = generar(args.partidas, args.players, escribir, args.modelo_dl, args.backend)

    arr = np.asarray(filas, dtype=np.float32)
    X, y = arr[:, :-1], arr[:, -1]
    np.savez_compressed(args.out, X=X, y=y)

    print(f"\nTerminado: {partidas_ok}/{args.partidas} partidas ok -> {len(y)} filas "
          f"en {args.out} ({time.perf_counter()-t0:.1f}s)")


if __name__ == "__main__":
    main()
