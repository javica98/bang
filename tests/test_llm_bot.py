"""Tests del bot LLM (Fase 3): sin clave de API configurada, toda decisión
de carta debe caer al fallback heurístico sin romper la partida. No hace
llamadas de red reales — eso requiere GEMINI_API_KEY/GOOGLE_API_KEY y se
prueba manualmente, no en la suite automática.
"""
import os
import random

import pytest

from sim.llm_bot import LLMBotAI
from sim.simulate import CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT
from sim.sim_io import SimIO
from bang_game import info_extract, create_players, Juego
from bot_ai import BotAI

VALID_GANADORES = {"Sheriff", "Forajidos", "Renegado"}


@pytest.fixture(autouse=True)
def _sin_clave_api(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def test_partida_con_llm_sin_clave_cae_a_heuristica():
    # Semilla fija: sin ella, bot0 a veces muere en la ronda 1 antes de
    # tomar ninguna decisión con 2+ opciones (partida perfectamente
    # válida, pero deja `metricas` vacío y el test no puede comprobar nada).
    random.seed(0)
    baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
    num_players = 4
    nombres = [f"Bot{i}" for i in range(num_players)]
    bots = {0: LLMBotAI(0)}
    for i in range(1, num_players):
        bots[i] = BotAI(i)
    io = SimIO(bots, max_pasos=1000)
    jugadores = create_players(num_players, nombres, personajes, roles, io=io)
    juego = Juego(jugadores, baraja, io=io)
    io.set_game(juego)
    juego.partida()

    assert juego.ganador in VALID_GANADORES
    llm = bots[0]
    assert len(llm.metricas) > 0
    assert all(m["fallback"] for m in llm.metricas)
    assert all("no configurada" in (m["error"] or "") for m in llm.metricas)


def test_extraer_opcion_tolera_ruido_en_la_respuesta():
    opciones = ["1", "2", "FIN"]
    assert LLMBotAI._extraer_opcion("FIN", opciones) == "FIN"
    assert LLMBotAI._extraer_opcion(" fin.\n", opciones) == "FIN"
    assert LLMBotAI._extraer_opcion("La respuesta es 2", opciones) == "2"
    assert LLMBotAI._extraer_opcion("3", opciones) is None
    assert LLMBotAI._extraer_opcion("", opciones) is None
    assert LLMBotAI._extraer_opcion(None, opciones) is None
