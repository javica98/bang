"""Simulador puro de partidas de BANG! — Fase 0 del roadmap de IA.

Ejecuta partidas completas en proceso, sin Flask ni HTTP: todos los
jugadores son bots (BotAI) resolviendo decisiones vía SimIO. Sirve como
base para generar datos y medir bots a gran escala (MCTS, entrenamiento
supervisado, self-play, benchmarks).

Uso:
    python sim/simulate.py -n 200 -p 4          # benchmark de 200 partidas
    python sim/simulate.py --debug -p 4         # 1 partida con log de decisiones
"""
import argparse
import builtins
import contextlib
import os
import statistics
import sys
import time
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bang_game import info_extract, create_players, Juego  # noqa: E402
from bot_ai import BotAI  # noqa: E402
from sim_io import SimIO, PasosExcedidos  # noqa: E402

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


def jugar_partida(num_players=4, nombres=None, debug=False, quiet=True, max_pasos=2000):
    """Juega una partida completa en proceso y devuelve un resumen del resultado.

    Args:
        num_players (int): Número de jugadores (4-7), todos bots.
        nombres (list[str] | None): Nombres de los jugadores. Por defecto Bot0..BotN.
        debug (bool): Si True, imprime cada decisión de bot (tipo, respuesta).
        quiet (bool): Si True, silencia los print() del motor de juego (rondas, etc).
        max_pasos (int | None): Corta la partida si supera este nº de decisiones,
            para que un bucle de bots no cuelgue un benchmark entero.

    Returns:
        dict: ganador, rondas, pasos, elapsed, roles, personajes, sobrevivientes.
            Si se corta por max_pasos, ganador es None y "error" = "max_pasos_excedido".
    """
    baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
    nombres = nombres or [f"Bot{i}" for i in range(num_players)]
    bots = {i: BotAI(i) for i in range(num_players)}
    io = SimIO(bots, debug=debug, max_pasos=max_pasos)

    jugadores = create_players(num_players, nombres, personajes, roles, io=io)
    juego = Juego(jugadores, baraja, io=io)
    io.set_game(juego)

    t0 = time.perf_counter()
    try:
        with _silenciar_print() if quiet and not debug else contextlib.nullcontext():
            juego.partida()
        error = None
    except PasosExcedidos:
        error = "max_pasos_excedido"
    elapsed = time.perf_counter() - t0

    return {
        "ganador": juego.ganador,
        "error": error,
        "rondas": juego.ronda,
        "pasos": io.pasos,
        "elapsed": elapsed,
        "roles": {j.idJugador: j.rol for j in juego.jugadores},
        "personajes": {j.idJugador: j.personaje.nombre for j in juego.jugadores},
        "sobrevivientes": [j.idJugador for j in juego.jugadores if not j.muerto],
    }


def benchmark(n, num_players=4, max_pasos=2000):
    """Juega `n` partidas seguidas y devuelve estadísticas agregadas de velocidad/resultado."""
    tiempos = []
    pasos = []
    ganadores = Counter()
    errores = Counter()

    t_total0 = time.perf_counter()
    for _ in range(n):
        r = jugar_partida(num_players=num_players, quiet=True, max_pasos=max_pasos)
        tiempos.append(r["elapsed"])
        pasos.append(r["pasos"])
        ganadores[r["ganador"]] += 1
        if r["error"]:
            errores[r["error"]] += 1
    t_total = time.perf_counter() - t_total0

    return {
        "n": n,
        "num_players": num_players,
        "tiempo_total": t_total,
        "partidas_por_segundo": n / t_total if t_total > 0 else float("inf"),
        "tiempo_medio_ms": statistics.mean(tiempos) * 1000,
        "tiempo_mediana_ms": statistics.median(tiempos) * 1000,
        "pasos_medios": statistics.mean(pasos),
        "ganadores": dict(ganadores),
        "errores": dict(errores),
    }


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="Simulador headless de BANG! (sin Flask)")
    parser.add_argument("-n", "--partidas", type=int, default=100, help="Número de partidas a simular")
    parser.add_argument("-p", "--players", type=int, default=4, choices=[4, 5, 6, 7], help="Jugadores por partida")
    parser.add_argument("--debug", action="store_true", help="Juega 1 sola partida mostrando cada decisión")
    parser.add_argument("--max-pasos", type=int, default=2000, help="Corta una partida colgada tras N decisiones")
    args = parser.parse_args()

    if args.debug:
        r = jugar_partida(num_players=args.players, debug=True, quiet=False, max_pasos=args.max_pasos)
        print(f"\nGanador: {r['ganador']} | rondas={r['rondas']} pasos={r['pasos']} "
              f"tiempo={r['elapsed'] * 1000:.1f}ms")
        print(f"Roles: {r['roles']}")
        return

    stats = benchmark(args.partidas, num_players=args.players, max_pasos=args.max_pasos)
    print(f"Partidas: {stats['n']} ({stats['num_players']} jugadores)")
    print(f"Tiempo total: {stats['tiempo_total']:.2f}s")
    print(f"Partidas/segundo: {stats['partidas_por_segundo']:.1f}")
    print(f"Tiempo medio/partida: {stats['tiempo_medio_ms']:.2f} ms (mediana {stats['tiempo_mediana_ms']:.2f} ms)")
    print(f"Pasos medios/partida: {stats['pasos_medios']:.1f}")
    print(f"Ganadores: {stats['ganadores']}")
    if stats["errores"]:
        print(f"Errores: {stats['errores']}")


if __name__ == "__main__":
    main()
