import pytest

from ClasesAux import Carta, Personaje, Jugador
from bang_game import Juego


class FakeIO:
    """Scripted io adapter for Juego: no blocking input, answers come from a queue.

    Push expected answers with `queue(...)` (or pass them to the constructor) in the
    exact order the game logic will ask for them. Every io method Juego calls pops the
    next value off the queue and returns it directly (bypassing text/option formatting).
    Popping from an empty queue raises AssertionError so an unscripted prompt fails the
    test loudly instead of hanging.
    """

    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self.current_jugador = None
        self.calls = []

    def queue(self, *values):
        self._responses.extend(values)
        return self

    def _next(self, kind):
        self.calls.append(kind)
        if not self._responses:
            raise AssertionError(f"FakeIO: no scripted response left for '{kind}'")
        return self._responses.pop(0)

    def prompt(self, text, options=None):
        return self._next("prompt")

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        return self._next("elegir_carta")

    def elegir_personaje(self, nombre_jugador, rol, personaje_a, personaje_b):
        return self._next("elegir_personaje")

    def elegir_jugador(self, jugadores, text, jugadores_fuera_alcance=None):
        return self._next("elegir_jugador")

    def elegir_carta_rival(self, rival, text):
        return self._next("elegir_carta_rival")

    def elegir_lucky_duke(self, jugador, carta1, carta2):
        return self._next("elegir_lucky_duke")

    def elegir_robo_jesse(self, jugador, rivales):
        return self._next("elegir_robo_jesse")

    def elegir_robo_pedro(self, jugador, carta_top):
        return self._next("elegir_robo_pedro")

    def elegir_kit_carlson(self, jugador, cartas):
        return self._next("elegir_kit_carlson")

    def elegir_almacen_carta(self, jugador, cartas):
        return self._next("elegir_almacen_carta")


_next_id_objeto = iter(range(1_000_000))


def make_carta(idClase=99, nombre="Carta de prueba", tipo="Efecto", numero=None, palo=None):
    carta = Carta(next(_next_id_objeto), idClase, nombre, tipo)
    carta.numero = numero
    carta.palo = palo
    return carta


def make_personaje(nombre="Personaje de prueba", vidas=4, idPersonaje=0):
    return Personaje(idPersonaje, nombre, vidas)


def make_jugador(idJugador, nombre=None, rol="Ayudante", personaje=None, cartas=None):
    nombre = nombre or f"Jugador{idJugador}"
    personaje = personaje or make_personaje()
    return Jugador(idJugador, nombre, personaje, rol, cartas)


def make_juego(num_jugadores=4, roles=None, io=None):
    """Builds a Juego with `num_jugadores` players and a deck deep enough for the
    initial deal (5 cards each), without touching cartas.csv/personajes.txt/roles.txt.
    """
    roles = roles or (["Sheriff"] + ["Ayudante", "Forajido", "Renegado", "Ayudante", "Forajido", "Ayudante"])[:num_jugadores]
    jugadores = [
        make_jugador(i, rol=roles[i])
        for i in range(num_jugadores)
    ]
    baraja = [make_carta() for _ in range(5 * num_jugadores + 10)]
    return Juego(jugadores, baraja, io=io or FakeIO())


@pytest.fixture
def fake_io():
    return FakeIO()


@pytest.fixture
def personaje_factory():
    return make_personaje


@pytest.fixture
def carta_factory():
    return make_carta


@pytest.fixture
def jugador_factory():
    return make_jugador


@pytest.fixture
def juego_factory():
    return make_juego
