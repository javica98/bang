"""Tests for card-effect methods in Juego.

Each test builds a minimal Juego via make_juego / make_carta and scripts FakeIO
with the exact prompts the game logic will fire, in order. Tests are grouped by
card type and cover: normal effect, edge-cases (no target, already equipped, etc.)
and interactions with character specials where relevant.
"""

import pytest

from bang_game import DISTANCIAS_ARMA
from tests.conftest import make_carta, make_juego, FakeIO


# ── helpers ──────────────────────────────────────────────────────────────────

def _set_hand(juego, id_jugador, *cartas):
    """Clears the player's hand and sets it to exactly the given cards.

    make_juego deals initial cards during __init__, so using this helper
    ensures carta at index 0 is always our test card, not a dealt one.
    """
    juego.jugadores[id_jugador].cartasMano.clear()
    for c in cartas:
        juego.jugadores[id_jugador].recibeCarta(c)


def _deal(juego, id_jugador, *cartas):
    """Appends cartas to the player's existing hand (preserves initial deal)."""
    for c in cartas:
        juego.jugadores[id_jugador].recibeCarta(c)


def _hand_nombres(juego, id_jugador):
    return [c.nombre for c in juego.jugadores[id_jugador].cartasMano]


# ── Cerveza ───────────────────────────────────────────────────────────────────

class TestCerveza:
    def test_recupera_una_vida(self):
        juego = make_juego(num_jugadores=4)
        jugador = juego.jugadores[0]
        jugador.vidas -= 1
        cerveza = make_carta(idClase=13, nombre="Cerveza")
        _set_hand(juego, 0, cerveza)
        vidas_antes = jugador.vidas
        juego.cerveza(0, 0)
        assert jugador.vidas == vidas_antes + 1

    def test_descarta_la_carta(self):
        juego = make_juego(num_jugadores=4)
        juego.jugadores[0].vidas -= 1
        cerveza = make_carta(idClase=13, nombre="Cerveza")
        _set_hand(juego, 0, cerveza)
        juego.cerveza(0, 0)
        assert cerveza not in juego.jugadores[0].cartasMano
        assert cerveza in juego.monton_descartes

    def test_no_supera_vidas_max(self):
        juego = make_juego(num_jugadores=4)
        jugador = juego.jugadores[0]
        cerveza = make_carta(idClase=13, nombre="Cerveza")
        _set_hand(juego, 0, cerveza)
        juego.cerveza(0, 0)
        assert jugador.vidas == jugador.vidasMax

    def test_sin_efecto_con_dos_jugadores_vivos(self):
        juego = make_juego(num_jugadores=4)
        juego.jugadores[1].muerto = True
        juego.jugadores[2].muerto = True
        jugador = juego.jugadores[0]
        jugador.vidas -= 1
        vidas_antes = jugador.vidas
        cerveza = make_carta(idClase=13, nombre="Cerveza")
        _set_hand(juego, 0, cerveza)
        juego.cerveza(0, 0)
        assert jugador.vidas == vidas_antes


# ── Saloon ────────────────────────────────────────────────────────────────────

class TestSaloon:
    def test_todos_los_vivos_recuperan_un_vida(self):
        juego = make_juego(num_jugadores=4)
        for j in juego.jugadores:
            j.vidas -= 1
        saloon = make_carta(idClase=19, nombre="Saloon")
        _set_hand(juego, 0, saloon)
        juego.saloon(0, 0)
        for j in juego.jugadores:
            assert j.vidas == j.vidasMax

    def test_no_afecta_a_muertos(self):
        juego = make_juego(num_jugadores=4)
        for j in juego.jugadores:
            j.vidas -= 1
        juego.jugadores[1].muerto = True
        vidas_muerto = juego.jugadores[1].vidas
        saloon = make_carta(idClase=19, nombre="Saloon")
        _set_hand(juego, 0, saloon)
        juego.saloon(0, 0)
        assert juego.jugadores[1].vidas == vidas_muerto


# ── Diligencia / Wells Fargo ──────────────────────────────────────────────────

class TestDiligencia:
    def test_roba_dos_cartas(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=21, nombre="Diligencia")
        _set_hand(juego, 0, carta)
        juego.diligencia(0, 0)
        # -1 jugada +2 robadas = +1 neto
        assert len(juego.jugadores[0].cartasMano) == 2

    def test_descarta_la_carta_jugada(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=21, nombre="Diligencia")
        _set_hand(juego, 0, carta)
        juego.diligencia(0, 0)
        assert carta in juego.monton_descartes


class TestWellsFargo:
    def test_roba_tres_cartas(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=22, nombre="Wells Fargo")
        _set_hand(juego, 0, carta)
        juego.wells_fargo(0, 0)
        # -1 jugada +3 robadas = +2 neto
        assert len(juego.jugadores[0].cartasMano) == 3


# ── Objetos equipables ────────────────────────────────────────────────────────

class TestMustang:
    def test_equipa_mustang_y_activa_flag(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=7, nombre="Mustang")
        _set_hand(juego, 0, carta)
        juego.mustang(0, 0)
        assert juego.jugadores[0].mustang is True
        assert carta in juego.jugadores[0].cartasEquipadas

    def test_no_permite_dos_mustang(self):
        juego = make_juego(num_jugadores=4)
        c1 = make_carta(idClase=7, nombre="Mustang")
        c2 = make_carta(idClase=7, nombre="Mustang")
        _set_hand(juego, 0, c1, c2)
        juego.mustang(0, 0)  # equipa c1
        juego.mustang(0, 0)  # segundo intento con c2 — debe ignorarse
        assert len([c for c in juego.jugadores[0].cartasEquipadas if c.idClase == 7]) == 1


class TestBarril:
    def test_equipa_barril_y_activa_flag(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=8, nombre="Barril")
        _set_hand(juego, 0, carta)
        juego.barril(0, 0)
        assert juego.jugadores[0].barril is True
        assert carta in juego.jugadores[0].cartasEquipadas

    def test_no_permite_dos_barriles(self):
        juego = make_juego(num_jugadores=4)
        c1 = make_carta(idClase=8, nombre="Barril")
        c2 = make_carta(idClase=8, nombre="Barril")
        _set_hand(juego, 0, c1, c2)
        juego.barril(0, 0)
        juego.barril(0, 0)
        assert len([c for c in juego.jugadores[0].cartasEquipadas if c.idClase == 8]) == 1


class TestMiraTelescopica:
    def test_equipa_mira_y_activa_flag(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=10, nombre="Mira Telescópica")
        _set_hand(juego, 0, carta)
        juego.mira_telescopica(0, 0)
        assert juego.jugadores[0].miraTelescopica is True
        assert carta in juego.jugadores[0].cartasEquipadas


# ── Armas ─────────────────────────────────────────────────────────────────────

class TestAnadirArma:
    @pytest.mark.parametrize("idClase", [1, 2, 3, 4, 5])
    def test_equipa_arma_y_actualiza_distancia(self, idClase):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=idClase, nombre=f"Arma{idClase}")
        _set_hand(juego, 0, carta)
        juego.anadir_arma(0, 0)
        jugador = juego.jugadores[0]
        assert jugador.arma == idClase
        assert jugador.distancia == DISTANCIAS_ARMA[idClase]

    def test_volcanic_activa_flag_y_fija_distancia_uno(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=1, nombre="Volcanic")
        _set_hand(juego, 0, carta)
        juego.anadir_arma(0, 0)
        assert juego.jugadores[0].volcanic is True
        assert juego.jugadores[0].distancia == 1

    def test_cambiar_arma_descarta_la_anterior(self):
        juego = make_juego(num_jugadores=4)
        c1 = make_carta(idClase=2, nombre="Schofield")
        c2 = make_carta(idClase=3, nombre="Remington")
        _set_hand(juego, 0, c1)
        juego.anadir_arma(0, 0)
        _set_hand(juego, 0, c2)
        juego.anadir_arma(0, 0)
        equipadas = juego.jugadores[0].cartasEquipadas
        assert len([c for c in equipadas if c.idClase in {2, 3}]) == 1
        assert c1 in juego.monton_descartes


# ── Bang ──────────────────────────────────────────────────────────────────────

class TestBang:
    def test_inflige_dano_si_enemigo_no_esquiva(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, carta)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes - 1

    def test_no_inflige_dano_si_enemigo_esquiva_con_fallaste(self):
        io = FakeIO()
        io.queue("SI")
        juego = make_juego(num_jugadores=4, io=io)
        carta_bang = make_carta(idClase=11, nombre="Bang")
        fallaste = make_carta(idClase=12, nombre="Fallaste")
        _set_hand(juego, 0, carta_bang)
        _set_hand(juego, 1, fallaste)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes
        assert fallaste in juego.monton_descartes

    def test_limite_un_bang_por_turno(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        b1 = make_carta(idClase=11, nombre="Bang")
        b2 = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, b1, b2)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)  # primer bang — funciona
        juego.bang(0, 1, 0)  # segundo bang — ignorado (contBang == 1)
        assert juego.jugadores[1].vidas == vidas_antes - 1

    def test_volcanic_permite_multiples_bangs(self):
        io = FakeIO()
        io.queue("NO", "NO")
        juego = make_juego(num_jugadores=4, io=io)
        juego.jugadores[0].volcanic = True
        b1 = make_carta(idClase=11, nombre="Bang")
        b2 = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, b1, b2)
        juego.bang(0, 1, 0)
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == juego.jugadores[1].vidasMax - 2

    def test_sin_objetivo_no_hace_nada(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, carta)
        vidas_antes = [j.vidas for j in juego.jugadores]
        juego.bang(0, None, 0)
        for j, v in zip(juego.jugadores, vidas_antes):
            assert j.vidas == v


# ── Indios ────────────────────────────────────────────────────────────────────

class TestIndios:
    def test_rival_sin_bang_pierde_vida(self):
        io = FakeIO()
        io.queue("NO", "NO", "NO")
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=14, nombre="Indios")
        _set_hand(juego, 0, carta)
        vidas_rivales = [juego.jugadores[i].vidas for i in range(1, 4)]
        juego.indios(0, 0)
        for i, vidas_antes in enumerate(vidas_rivales, start=1):
            assert juego.jugadores[i].vidas == vidas_antes - 1

    def test_rival_con_bang_esquiva(self):
        io = FakeIO()
        io.queue("SI", "NO", "NO")
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=14, nombre="Indios")
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, carta)
        _set_hand(juego, 1, bang)
        vidas_j1 = juego.jugadores[1].vidas
        vidas_j2 = juego.jugadores[2].vidas
        juego.indios(0, 0)
        assert juego.jugadores[1].vidas == vidas_j1
        assert juego.jugadores[2].vidas == vidas_j2 - 1


# ── Ametralladora ─────────────────────────────────────────────────────────────

class TestAmetralladora:
    def test_rival_sin_fallaste_pierde_vida(self):
        io = FakeIO()
        io.queue("NO", "NO", "NO")
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=16, nombre="Ametralladora")
        _set_hand(juego, 0, carta)
        vidas_rivales = [juego.jugadores[i].vidas for i in range(1, 4)]
        juego.ametralladora(0, 0)
        for i, vidas_antes in enumerate(vidas_rivales, start=1):
            assert juego.jugadores[i].vidas == vidas_antes - 1

    def test_rival_con_fallaste_esquiva(self):
        io = FakeIO()
        io.queue("SI", "NO", "NO")
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=16, nombre="Ametralladora")
        fallaste = make_carta(idClase=12, nombre="Fallaste")
        _set_hand(juego, 0, carta)
        _set_hand(juego, 1, fallaste)
        vidas_j1 = juego.jugadores[1].vidas
        juego.ametralladora(0, 0)
        assert juego.jugadores[1].vidas == vidas_j1


# ── Duelo ─────────────────────────────────────────────────────────────────────

class TestDuelo:
    def test_enemigo_sin_bang_pierde_vida(self):
        io = FakeIO()
        io.queue("NO")  # enemigo preguntado primero, no tiene bang
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=15, nombre="Duelo")
        _set_hand(juego, 0, carta)
        _set_hand(juego, 1)  # sin cartas para asegurar que no puede responder
        vidas_antes = juego.jugadores[1].vidas
        juego.duelo(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes - 1

    def test_retador_pierde_si_no_tiene_bang_tras_intercambio(self):
        io = FakeIO()
        io.queue("SI", "NO")  # enemigo usa bang, retador no puede responder
        juego = make_juego(num_jugadores=4, io=io)
        carta_duelo = make_carta(idClase=15, nombre="Duelo")
        bang_enemigo = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, carta_duelo)
        _set_hand(juego, 1, bang_enemigo)
        vidas_antes = juego.jugadores[0].vidas
        juego.duelo(0, 1, 0)
        assert juego.jugadores[0].vidas == vidas_antes - 1

    def test_sin_objetivo_no_hace_nada(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=15, nombre="Duelo")
        _set_hand(juego, 0, carta)
        vidas = [j.vidas for j in juego.jugadores]
        juego.duelo(0, None, 0)
        for j, v in zip(juego.jugadores, vidas):
            assert j.vidas == v


# ── Pánico ────────────────────────────────────────────────────────────────────

class TestPanico:
    def test_roba_carta_de_la_mano_del_rival(self):
        juego = make_juego(num_jugadores=4)
        carta_panico = make_carta(idClase=17, nombre="Pánico")
        carta_rival = make_carta(idClase=99, nombre="CartaRival")
        _set_hand(juego, 0, carta_panico)
        _set_hand(juego, 1, carta_rival)
        juego.panico(0, 1, 0, ("mano", 0))
        assert carta_rival in juego.jugadores[0].cartasMano
        assert carta_rival not in juego.jugadores[1].cartasMano

    def test_sin_objetivo_no_hace_nada(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=17, nombre="Pánico")
        _set_hand(juego, 0, carta)
        juego.panico(0, None, 0, None)
        assert carta in juego.jugadores[0].cartasMano

    def test_rival_sin_cartas_no_hace_nada(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=17, nombre="Pánico")
        _set_hand(juego, 0, carta)
        _set_hand(juego, 1)  # sin cartas
        juego.panico(0, 1, 0, None)
        assert carta in juego.jugadores[0].cartasMano


# ── Ingeniería Explosiva ──────────────────────────────────────────────────────

class TestIngExplosiva:
    def test_descarta_carta_de_la_mano_del_rival(self):
        juego = make_juego(num_jugadores=4)
        carta_ing = make_carta(idClase=18, nombre="Ing. Explosiva")
        carta_rival = make_carta(idClase=99, nombre="CartaRival")
        _set_hand(juego, 0, carta_ing)
        _set_hand(juego, 1, carta_rival)
        juego.ingExplosiva(0, 1, 0, ("mano", 0))
        assert carta_rival not in juego.jugadores[1].cartasMano
        assert carta_rival in juego.monton_descartes

    def test_descarta_carta_equipada_del_rival(self):
        juego = make_juego(num_jugadores=4)
        carta_ing = make_carta(idClase=18, nombre="Ing. Explosiva")
        carta_equipada = make_carta(idClase=7, nombre="Mustang")
        _set_hand(juego, 0, carta_ing)
        juego.jugadores[1].equipaCarta(carta_equipada)
        juego.ingExplosiva(0, 1, 0, ("equipada", 0))
        assert carta_equipada not in juego.jugadores[1].cartasEquipadas
        assert carta_equipada in juego.monton_descartes

    def test_sin_objetivo_no_hace_nada(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=18, nombre="Ing. Explosiva")
        _set_hand(juego, 0, carta)
        juego.ingExplosiva(0, None, 0, None)
        assert carta in juego.jugadores[0].cartasMano


# ── Almacén ───────────────────────────────────────────────────────────────────

class TestAlmacen:
    def test_cada_jugador_recibe_una_carta(self):
        io = FakeIO()
        # elegir_almacen_carta debe devolver int; cada jugador elige índice 0
        io.queue(0, 0, 0, 0)
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=20, nombre="Almacén")
        _set_hand(juego, 0, carta)
        manos_antes = [len(j.cartasMano) for j in juego.jugadores]
        juego.almacen(0, 0)
        # jugador 0: -1 (almacén jugado) +1 (carta elegida) = sin cambio neto
        # jugadores 1-3: +1 carta cada uno
        assert len(juego.jugadores[0].cartasMano) == manos_antes[0]
        for i in range(1, 4):
            assert len(juego.jugadores[i].cartasMano) == manos_antes[i] + 1

    def test_carta_del_almacen_se_descarta(self):
        io = FakeIO()
        io.queue(0, 0, 0, 0)
        juego = make_juego(num_jugadores=4, io=io)
        carta = make_carta(idClase=20, nombre="Almacén")
        _set_hand(juego, 0, carta)
        juego.almacen(0, 0)
        assert carta in juego.monton_descartes
