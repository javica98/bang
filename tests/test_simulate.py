"""Tests del simulador headless (Fase 0): valida que SimIO/jugar_partida
producen partidas completas y coherentes con las mismas reglas que el
motor web, sin pasar por Flask/HTTP.
"""
import os
from collections import Counter

import pytest

from sim.simulate import ROLES_TXT, jugar_partida

VALID_GANADORES = {"Sheriff", "Forajidos", "Renegado"}


def _roles_esperados(num_players):
    with open(ROLES_TXT, encoding="utf-8") as f:
        roles = [line.strip() for line in f if line.strip()]
    return Counter(roles[:num_players])


@pytest.mark.parametrize("num_players", [4, 5, 6, 7])
def test_partida_completa_sin_errores(num_players):
    r = jugar_partida(num_players=num_players, max_pasos=3000)
    assert r["error"] is None
    assert r["ganador"] in VALID_GANADORES
    assert r["rondas"] >= 1
    assert r["pasos"] > 0


@pytest.mark.parametrize("num_players", [4, 5, 6, 7])
def test_reparto_de_roles_correcto(num_players):
    r = jugar_partida(num_players=num_players, max_pasos=3000)
    assert Counter(r["roles"].values()) == _roles_esperados(num_players)


@pytest.mark.parametrize("num_players", [4, 5, 6, 7])
def test_todos_los_jugadores_tienen_personaje_distinto(num_players):
    r = jugar_partida(num_players=num_players, max_pasos=3000)
    nombres = list(r["personajes"].values())
    assert len(nombres) == len(set(nombres)) == num_players


def test_muchas_partidas_seguidas_no_cuelgan():
    """Corre una tanda para detectar bucles de bots (max_pasos) o excepciones."""
    for _ in range(30):
        r = jugar_partida(num_players=4, max_pasos=2000)
        assert r["error"] is None, r
