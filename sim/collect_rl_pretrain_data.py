"""Genera datos (estado, acción) en el formato unificado Discrete(29) que
usa rl_env.py (carta + a quién apuntar + esquivar), para pre-entrenar la
política de MaskablePPO por imitación antes de arrancar el self-play real
(Fase 5).

Dos modos:
  --experto heuristico (por defecto): self-play de los 4 jugadores con
      BotAI, se graban las decisiones de TODOS — barato, mismo espíritu
      que collect_dataset.py (Fase 4).
  --experto mcts: solo el jugador 0 es MCTSBotAI (los otros 3 son BotAI,
      para no disparar el coste x4), y solo se graban SUS decisiones de
      carta (a quién apuntar / esquivar los sigue decidiendo la
      heurística interna de MCTSBotAI igual que en el resto de fases, así
      que grabarlas no aportaría nada distinto a "heuristico" para esos
      dos tipos). Mucho más lento: usa un presupuesto de tiempo pequeño
      para que generar unos cientos de partidas sea viable.

Uso:
    python sim/collect_rl_pretrain_data.py -n 5000 -o rl_pretrain_data.npz
    python sim/collect_rl_pretrain_data.py --experto mcts -n 500 --presupuesto-mcts 0.03 -o rl_pretrain_data_mcts.npz
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
from features import nombre_de_opcion  # noqa: E402
from mcts_bot import MCTSBotAI  # noqa: E402
from rl_common import (  # noqa: E402
    TIPO_CARTA, TIPO_JUGADOR, TIPO_ESQUIVAR, VOCABULARIO_CARTAS,
    OFFSET_CARTA, OFFSET_JUGADOR, OFFSET_ESQUIVAR, N_RIVALES_ACCION,
    observacion, offset_relativo, es_prompt_esquivar,
)

CARTAS_CSV = os.path.join(BASE_DIR, "cartas.csv")
PERSONAJES_TXT = os.path.join(BASE_DIR, "personajes.txt")
ROLES_TXT = os.path.join(BASE_DIR, "roles.txt")


def _mano_de(jugador):
    return [
        {"nombre": c.nombre, "tipo": c.tipo, "idClase": c.idClase, "indice": i}
        for i, c in enumerate(jugador.cartasMano)
    ]


@contextlib.contextmanager
def _silenciar_print():
    orig = builtins.print
    builtins.print = lambda *a, **k: None
    try:
        yield
    finally:
        builtins.print = orig


class ColectorRL(SimIO):
    """Registra (obs, acción_global, máscara) por cada decisión de carta /
    a quién apuntar / esquivar, para los jugadores en `jugadores_a_grabar`
    (None = todos)."""

    def __init__(self, bots, writer, jugadores_a_grabar=None, max_pasos=None):
        super().__init__(bots, max_pasos=max_pasos)
        self._writer = writer
        self._jugadores_a_grabar = jugadores_a_grabar

    def _grabar(self, jid):
        return self._jugadores_a_grabar is None or jid in self._jugadores_a_grabar

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        mano = _mano_de(jugador)
        pregunta = {
            "texto": text, "opciones": list(opciones), "permitir_fin": permitir_fin,
            "permitir_poder": permitir_poder, "jugador_id": jugador.idJugador, "mano": mano,
        }
        resp = super().elegir_carta(jugador, text, opciones, permitir_fin, permitir_poder)
        if self._grabar(jugador.idJugador) and (len(opciones) + permitir_fin + permitir_poder) > 1:
            nombre = nombre_de_opcion(resp, mano)
            if nombre is not None and nombre in VOCABULARIO_CARTAS:
                obs, mask = observacion(TIPO_CARTA, pregunta, jugador, self.juego)
                self._writer(obs, OFFSET_CARTA + VOCABULARIO_CARTAS.index(nombre), mask)
        return resp

    def elegir_jugador(self, jugadores, text, jugadores_fuera_alcance=None):
        asking_id = self._asking_id
        jugador = self.current_jugador
        validos = [j.idJugador for j in jugadores]
        pregunta = {
            "texto": text, "jugadores_validos": validos,
            "jugadores_fuera_alcance": [j.idJugador for j in (jugadores_fuera_alcance or [])],
            "mano": _mano_de(jugador) if jugador else [],
        }
        resp = super().elegir_jugador(jugadores, text, jugadores_fuera_alcance)
        if jugador is not None and self._grabar(asking_id) and len(validos) > 1 and resp is not None:
            n = len(self.juego.jugadores)
            offset = offset_relativo(jugador.idJugador, resp, n)
            if 1 <= offset <= N_RIVALES_ACCION:
                obs, mask = observacion(TIPO_JUGADOR, pregunta, jugador, self.juego)
                self._writer(obs, OFFSET_JUGADOR + (offset - 1), mask)
        return resp

    def prompt(self, text, options=None):
        if self.current_jugador is not None:
            self._asking_id = self.current_jugador.idJugador
        asking_id, jugador = self._asking_id, self.current_jugador
        pregunta_bruta = {"texto": text, "opciones": options or []}
        resp = super().prompt(text, options)
        if (jugador is not None and self._grabar(asking_id)
                and es_prompt_esquivar(pregunta_bruta) and resp in ("SI", "NO")):
            pregunta = dict(pregunta_bruta)
            pregunta["mano"] = _mano_de(jugador)
            obs, mask = observacion(TIPO_ESQUIVAR, pregunta, jugador, self.juego)
            self._writer(obs, OFFSET_ESQUIVAR + (0 if resp == "SI" else 1), mask)
        return resp


def generar(n_partidas, num_players, escribir, experto, presupuesto_mcts, max_pasos, progreso_cada):
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
        io = ColectorRL(bots, writer=escribir, jugadores_a_grabar=jugadores_a_grabar, max_pasos=max_pasos)
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
    parser = argparse.ArgumentParser(description="Genera datos de imitación en formato RL (Fase 5)")
    parser.add_argument("-n", "--partidas", type=int, default=5000)
    parser.add_argument("-p", "--players", type=int, default=4, choices=[4, 5, 6, 7])
    parser.add_argument("-o", "--out", type=str, default="rl_pretrain_data.npz")
    parser.add_argument("--experto", choices=["heuristico", "mcts"], default="heuristico")
    parser.add_argument("--presupuesto-mcts", type=float, default=0.03)
    parser.add_argument("--max-pasos", type=int, default=1500)
    parser.add_argument("--progreso-cada", type=int, default=None)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    progreso_cada = args.progreso_cada or (50 if args.experto == "mcts" else 1000)

    obs_buf, acc_buf, mask_buf = [], [], []

    def escribir(obs, accion, mask):
        obs_buf.append(obs)
        acc_buf.append(accion)
        mask_buf.append(mask)

    t0 = time.perf_counter()
    partidas_ok = generar(args.partidas, args.players, escribir, args.experto,
                           args.presupuesto_mcts, args.max_pasos, progreso_cada)

    obs_arr = np.asarray(obs_buf, dtype=np.float32)
    acc_arr = np.asarray(acc_buf, dtype=np.int64)
    mask_arr = np.asarray(mask_buf, dtype=bool)
    np.savez_compressed(args.out, obs=obs_arr, acciones=acc_arr, mascaras=mask_arr)

    print(f"\nTerminado ({args.experto}): {partidas_ok}/{args.partidas} partidas ok -> "
          f"{len(acc_arr)} decisiones en {args.out} ({time.perf_counter()-t0:.1f}s)")


if __name__ == "__main__":
    main()
