"""Tests del bot MCTS/UCT (Fase 2): partidas completas sin errores, con un
presupuesto de tiempo mínimo para que la suite siga siendo rápida — esto
no mide la calidad de las decisiones, solo que la integración no rompe
nada (mundo muestreado, clonado de estado, reanudar turno en el clon...).
"""
import pytest

from sim.mcts_bot import MCTSBotAI
from sim.simulate import CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT
from sim.sim_io import SimIO
from bang_game import info_extract, create_players, Juego
from bot_ai import BotAI

VALID_GANADORES = {"Sheriff", "Forajidos", "Renegado"}


@pytest.mark.parametrize("num_players", [4, 5])
def test_partida_con_mcts_termina_sin_errores(num_players):
    baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
    nombres = [f"Bot{i}" for i in range(num_players)]
    bots = {0: MCTSBotAI(0, presupuesto_s=0.01)}
    for i in range(1, num_players):
        bots[i] = BotAI(i)
    io = SimIO(bots, max_pasos=1000)
    jugadores = create_players(num_players, nombres, personajes, roles, io=io)
    juego = Juego(jugadores, baraja, io=io)
    io.set_game(juego)
    juego.partida()
    assert juego.ganador in VALID_GANADORES


def test_mcts_no_reasigna_rol_propio_ni_del_sheriff():
    """El muestreo de mundos debe respetar mi rol real y el del Sheriff."""
    baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
    nombres = [f"Bot{i}" for i in range(4)]
    bots = {0: MCTSBotAI(0, presupuesto_s=0.01)}
    for i in range(1, 4):
        bots[i] = BotAI(i)
    io = SimIO(bots, max_pasos=1000)
    jugadores = create_players(4, nombres, personajes, roles, io=io)
    juego = Juego(jugadores, baraja, io=io)
    io.set_game(juego)

    mcts = bots[0]
    mcts._heuristico._inicializar(juego)
    mi_rol_real = juego.jugadores[0].rol
    sheriff_id = next(j.idJugador for j in juego.jugadores if j.rol == "Sheriff")
    sheriff_rol_real = "Sheriff"

    from sim.mcts_bot import _clonar_juego, _muestrear_mundo
    for _ in range(20):
        clon = _clonar_juego(juego)
        _muestrear_mundo(clon, 0, mcts._heuristico.creencias)
        assert clon.jugadores[0].rol == mi_rol_real
        assert clon.jugadores[sheriff_id].rol == sheriff_rol_real
