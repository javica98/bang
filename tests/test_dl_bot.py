"""Tests del bot de Deep Learning supervisado (Fase 4): partidas completas
sin errores para los tres backends, usando los modelos ya entrenados en
sim/modelo_sklearn.joblib, sim/modelo_torch.pt y sim/modelo_xgboost.json.
"""
import os

import pytest

from sim.dl_bot import DLBotAI, MODELO_SKLEARN_DEFECTO, MODELO_TORCH_DEFECTO, MODELO_XGBOOST_DEFECTO
from sim.simulate import CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT
from sim.sim_io import SimIO
from bang_game import info_extract, create_players, Juego
from bot_ai import BotAI

VALID_GANADORES = {"Sheriff", "Forajidos", "Renegado"}

_FALTA_SKLEARN = not os.path.exists(MODELO_SKLEARN_DEFECTO)
_FALTA_TORCH = not os.path.exists(MODELO_TORCH_DEFECTO)
_FALTA_XGBOOST = not os.path.exists(MODELO_XGBOOST_DEFECTO)


def _jugar(backend, num_players=4):
    baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
    nombres = [f"Bot{i}" for i in range(num_players)]
    bots = {0: DLBotAI(0, backend=backend)}
    for i in range(1, num_players):
        bots[i] = BotAI(i)
    io = SimIO(bots, max_pasos=2000)
    jugadores = create_players(num_players, nombres, personajes, roles, io=io)
    juego = Juego(jugadores, baraja, io=io)
    io.set_game(juego)
    juego.partida()
    return juego


@pytest.mark.skipif(_FALTA_SKLEARN, reason="modelo_sklearn.joblib no entrenado todavía")
def test_partida_con_dl_sklearn_termina_sin_errores():
    juego = _jugar("sklearn")
    assert juego.ganador in VALID_GANADORES


@pytest.mark.skipif(_FALTA_TORCH, reason="modelo_torch.pt no entrenado todavía")
def test_partida_con_dl_torch_termina_sin_errores():
    juego = _jugar("torch")
    assert juego.ganador in VALID_GANADORES


@pytest.mark.skipif(_FALTA_XGBOOST, reason="modelo_xgboost.json no entrenado todavía")
def test_partida_con_dl_xgboost_termina_sin_errores():
    juego = _jugar("xgboost")
    assert juego.ganador in VALID_GANADORES
