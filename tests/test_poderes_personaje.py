"""Tests for character special powers.

Each test exercises one character's ability in isolation using FakeIO + make_juego.
_set_hand() clears the initial dealt hand so card indices are predictable.
"""

import pytest

from tests.conftest import make_carta, make_juego, make_personaje, FakeIO


def _set_hand(juego, id_jugador, *cartas):
    juego.jugadores[id_jugador].cartasMano.clear()
    for c in cartas:
        juego.jugadores[id_jugador].recibeCarta(c)


def _personaje(juego, id_jugador, nombre, vidas=4):
    juego.jugadores[id_jugador].personaje = make_personaje(nombre=nombre, vidas=vidas)


# ── Willy the Kid ─────────────────────────────────────────────────────────────

class TestWillyTheKid:
    def test_puede_jugar_multiples_bangs(self):
        io = FakeIO()
        io.queue("NO", "NO", "NO")  # enemigo no esquiva en ninguno de los 3 bangs
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Willy the Kid")
        b1 = make_carta(idClase=11, nombre="Bang")
        b2 = make_carta(idClase=11, nombre="Bang")
        b3 = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, b1, b2, b3)
        juego.bang(0, 1, 0)
        juego.bang(0, 1, 0)
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == juego.jugadores[1].vidasMax - 3

    def test_jugador_normal_solo_puede_un_bang(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        b1 = make_carta(idClase=11, nombre="Bang")
        b2 = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, b1, b2)
        juego.bang(0, 1, 0)
        juego.bang(0, 1, 0)  # ignorado
        assert juego.jugadores[1].vidas == juego.jugadores[1].vidasMax - 1


# ── Slab the Killer ───────────────────────────────────────────────────────────

class TestSlabTheKiller:
    def test_un_fallaste_no_esquiva(self):
        io = FakeIO()
        io.queue("SI", "NO")  # 1er fallaste → insuficiente; no tiene 2º
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Slab the Killer")
        bang = make_carta(idClase=11, nombre="Bang")
        fallaste = make_carta(idClase=12, nombre="Fallaste")
        _set_hand(juego, 0, bang)
        _set_hand(juego, 1, fallaste)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes - 1

    def test_dos_fallastes_esquivan(self):
        io = FakeIO()
        io.queue("SI", "SI")  # 2 fallastes → esquiva
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Slab the Killer")
        bang = make_carta(idClase=11, nombre="Bang")
        f1 = make_carta(idClase=12, nombre="Fallaste")
        f2 = make_carta(idClase=12, nombre="Fallaste")
        _set_hand(juego, 0, bang)
        _set_hand(juego, 1, f1, f2)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes


# ── Jourdonnais ───────────────────────────────────────────────────────────────

class TestJourdonnais:
    def test_barril_innato_esquiva_con_corazones(self):
        """Jourdonnais siempre intenta el chequeo de barril; si saca ♥ esquiva el Bang."""
        io = FakeIO()
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "Jourdonnais")
        # _draw_from_deck usa pop() → la carta al final del mazo es la primera robada
        carta_corazones = make_carta(palo="Corazones", numero=5)
        juego.baraja.append(carta_corazones)
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes  # esquivó

    def test_barril_innato_no_esquiva_con_picas(self):
        """Si el chequeo no es ♥, Jourdonnais recibe el daño igual."""
        io = FakeIO()
        io.queue("NO")  # no tiene Fallaste para esquivar
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "Jourdonnais")
        carta_picas = make_carta(palo="Picas", numero=3)
        juego.baraja.append(carta_picas)
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes - 1


# ── Calamity Janet ────────────────────────────────────────────────────────────

class TestCalamityJanet:
    def test_puede_usar_bang_como_fallaste(self):
        io = FakeIO()
        io.queue("SI")  # quiere esquivar con Bang (como Fallaste)
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "Calamity Janet")
        bang_atacante = make_carta(idClase=11, nombre="Bang")
        bang_respuesta = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang_atacante)
        _set_hand(juego, 1, bang_respuesta)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes  # esquivó con Bang

    def test_jugador_normal_no_puede_usar_bang_como_fallaste(self):
        io = FakeIO()
        io.queue("SI")  # quiere esquivar, pero solo tiene Bang (no Fallaste)
        juego = make_juego(num_jugadores=4, io=io)
        bang_atacante = make_carta(idClase=11, nombre="Bang")
        bang_respuesta = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang_atacante)
        _set_hand(juego, 1, bang_respuesta)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes - 1  # no esquivó


# ── Rose Doolan ───────────────────────────────────────────────────────────────

class TestRoseDoolan:
    def test_ve_distancia_reducida_en_uno(self):
        juego = make_juego(num_jugadores=5)
        _personaje(juego, 0, "Rose Doolan")
        # Sin poder: 0→2 es distancia 2; con Rose Doolan es 1
        assert juego.distancia(0, 2) == 1

    def test_no_baja_de_uno(self):
        juego = make_juego(num_jugadores=4)
        _personaje(juego, 0, "Rose Doolan")
        assert juego.distancia(0, 1) == 1  # mínimo 1


# ── Paul Regret ───────────────────────────────────────────────────────────────

class TestPaulRegret:
    def test_los_rivales_lo_ven_mas_lejos(self):
        juego = make_juego(num_jugadores=5)
        _personaje(juego, 2, "Paul Regret")
        # Sin poder: 0→2 es 2; con Paul Regret es 3
        assert juego.distancia(0, 2) == 3

    def test_no_afecta_a_distancia_desde_paul_regret(self):
        juego = make_juego(num_jugadores=5)
        _personaje(juego, 2, "Paul Regret")
        # Paul Regret atacando a otros no tiene penalización
        assert juego.distancia(2, 0) == 2


# ── Bart Cassidy ──────────────────────────────────────────────────────────────

class TestBartCassidy:
    def test_roba_carta_al_perder_vida(self):
        io = FakeIO()
        io.queue("NO")  # no esquiva el bang
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "Bart Cassidy")
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        _set_hand(juego, 1)
        mano_antes = len(juego.jugadores[1].cartasMano)
        juego.bang(0, 1, 0)
        # Perdió 1 vida → debería haber robado 1 carta
        assert len(juego.jugadores[1].cartasMano) == mano_antes + 1

    def test_jugador_normal_no_roba_al_perder_vida(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        _set_hand(juego, 1)
        mano_antes = len(juego.jugadores[1].cartasMano)
        juego.bang(0, 1, 0)
        assert len(juego.jugadores[1].cartasMano) == mano_antes  # sin robo extra


# ── El Gringo ─────────────────────────────────────────────────────────────────

class TestElGringo:
    def test_roba_carta_del_atacante_al_perder_vida(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "El Gringo")
        bang = make_carta(idClase=11, nombre="Bang")
        carta_extra = make_carta(idClase=99, nombre="CartaAtacante")
        _set_hand(juego, 0, bang, carta_extra)
        _set_hand(juego, 1)
        juego.bang(0, 1, 0)
        # El Gringo debe haber robado 1 carta de la mano del jugador 0
        total_mano_0 = len(juego.jugadores[0].cartasMano)
        total_mano_1 = len(juego.jugadores[1].cartasMano)
        assert total_mano_0 + total_mano_1 == 1  # bang descartado, carta_extra pasó a gringo

    def test_no_roba_si_atacante_sin_cartas(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "El Gringo")
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        _set_hand(juego, 1)
        juego.bang(0, 1, 0)
        # Atacante no tenía más cartas → El Gringo no roba nada
        assert len(juego.jugadores[1].cartasMano) == 0


# ── Suzy Lafayette ────────────────────────────────────────────────────────────

class TestSuzyLafayette:
    def test_roba_carta_al_quedarse_sin_mano(self):
        juego = make_juego(num_jugadores=4)
        _personaje(juego, 0, "Suzy Lafayette")
        carta = make_carta(idClase=13, nombre="Cerveza")
        _set_hand(juego, 0, carta)
        juego.jugadores[0].vidas -= 1  # para que cerveza tenga efecto
        juego.cerveza(0, 0)  # juega y descarta la única carta → mano vacía → roba 1
        assert len(juego.jugadores[0].cartasMano) == 1

    def test_jugador_normal_no_roba_al_quedarse_sin_mano(self):
        juego = make_juego(num_jugadores=4)
        carta = make_carta(idClase=13, nombre="Cerveza")
        _set_hand(juego, 0, carta)
        juego.jugadores[0].vidas -= 1
        juego.cerveza(0, 0)
        assert len(juego.jugadores[0].cartasMano) == 0


# ── Sid Ketchum ───────────────────────────────────────────────────────────────

class TestSidKetchum:
    def test_descarta_dos_cartas_para_ganar_vida(self):
        io = FakeIO()
        io.queue("SI", "1", "1", "NO")  # acepta, descarta índice 1, luego 1, luego no más
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Sid Ketchum")
        c1 = make_carta(idClase=99, nombre="C1")
        c2 = make_carta(idClase=99, nombre="C2")
        _set_hand(juego, 0, c1, c2)
        juego.jugadores[0].vidas -= 1
        vidas_antes = juego.jugadores[0].vidas
        juego.sid_ketchum(0)
        assert juego.jugadores[0].vidas == vidas_antes + 1
        assert len(juego.jugadores[0].cartasMano) == 0

    def test_no_actua_si_rechaza(self):
        io = FakeIO()
        io.queue("NO")
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Sid Ketchum")
        c1 = make_carta(idClase=99, nombre="C1")
        c2 = make_carta(idClase=99, nombre="C2")
        _set_hand(juego, 0, c1, c2)
        juego.jugadores[0].vidas -= 1
        vidas_antes = juego.jugadores[0].vidas
        juego.sid_ketchum(0)
        assert juego.jugadores[0].vidas == vidas_antes
        assert len(juego.jugadores[0].cartasMano) == 2


# ── Lucky Duke ────────────────────────────────────────────────────────────────

class TestLuckyDuke:
    def test_elige_corazones_y_esquiva(self):
        """Lucky Duke roba 2 cartas; FakeIO devuelve directamente la Carta elegida."""
        io = FakeIO()
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "Lucky Duke")
        juego.jugadores[1].barril = True

        carta_corazones = make_carta(palo="Corazones", numero=7)
        carta_picas = make_carta(palo="Picas", numero=3)
        # pop() saca el último → baraja: [..., carta_picas, carta_corazones]
        # 1er pop = carta_corazones, 2º pop = carta_picas
        juego.baraja.extend([carta_picas, carta_corazones])

        io.queue(carta_corazones)  # FakeIO devuelve la Carta directamente
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes  # eligió ♥ → esquivó

    def test_elige_picas_y_recibe_dano(self):
        io = FakeIO()
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 1, "Lucky Duke")
        juego.jugadores[1].barril = True

        carta_corazones = make_carta(palo="Corazones", numero=7)
        carta_picas = make_carta(palo="Picas", numero=3)
        juego.baraja.extend([carta_picas, carta_corazones])

        io.queue(carta_picas)   # elige ♠ → no esquiva por barril
        io.queue("NO")          # tampoco tiene Fallaste
        bang = make_carta(idClase=11, nombre="Bang")
        _set_hand(juego, 0, bang)
        vidas_antes = juego.jugadores[1].vidas
        juego.bang(0, 1, 0)
        assert juego.jugadores[1].vidas == vidas_antes - 1


# ── Black Jack ────────────────────────────────────────────────────────────────

class TestBlackJack:
    def test_roba_carta_extra_si_segunda_es_roja(self):
        """_draw_from_deck usa pop() → último elemento = primera carta robada.
        La 2ª carta robada (la que se muestra) debe ser la segunda en ser popeada."""
        juego = make_juego(num_jugadores=4)
        _personaje(juego, 0, "Black Jack")
        carta_1a = make_carta()
        carta_roja = make_carta(palo="Corazones", numero=5)  # 2ª carta → mostrada
        # pop order: carta_1a (last), carta_roja (second-to-last)
        # → baraja must end with: [..., carta_roja, carta_1a]
        juego.baraja.extend([carta_roja, carta_1a])
        _set_hand(juego, 0)
        juego._fase_robo(0)
        assert len(juego.jugadores[0].cartasMano) == 3

    def test_no_roba_extra_si_segunda_es_negra(self):
        juego = make_juego(num_jugadores=4)
        _personaje(juego, 0, "Black Jack")
        carta_1a = make_carta()
        carta_negra = make_carta(palo="Picas", numero=5)
        juego.baraja.extend([carta_negra, carta_1a])
        _set_hand(juego, 0)
        juego._fase_robo(0)
        assert len(juego.jugadores[0].cartasMano) == 2


# ── Jesse Jones ───────────────────────────────────────────────────────────────

class TestJesseJones:
    def test_roba_del_rival_si_elige_robar(self):
        io = FakeIO()
        io.queue(1)  # elige robar del jugador 1 (id_rival=1)
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Jesse Jones")
        carta_rival = make_carta(idClase=99, nombre="CartaRival")
        _set_hand(juego, 0)
        _set_hand(juego, 1, carta_rival)
        juego._fase_robo(0)
        # Jesse roba 1 del rival + 1 del mazo = 2 cartas en mano
        assert len(juego.jugadores[0].cartasMano) == 2
        assert carta_rival in juego.jugadores[0].cartasMano

    def test_roba_del_mazo_si_rechaza_rival(self):
        io = FakeIO()
        io.queue(None)  # elige no robar de ningún rival
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Jesse Jones")
        _set_hand(juego, 0)
        juego._fase_robo(0)
        assert len(juego.jugadores[0].cartasMano) == 2


# ── Kit Carlson ───────────────────────────────────────────────────────────────

class TestKitCarlson:
    def test_devuelve_la_carta_elegida_al_mazo(self):
        io = FakeIO()
        io.queue(2)  # devuelve la carta en posición 2 de las 3
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Kit Carlson")
        c_devuelta = make_carta(idClase=99, nombre="Devuelta")
        juego.baraja.insert(0, c_devuelta)  # será la 3ª carta vista
        _set_hand(juego, 0)
        baraja_antes = len(juego.baraja)
        juego._fase_robo(0)
        assert len(juego.jugadores[0].cartasMano) == 2
        assert c_devuelta in juego.baraja


# ── Pedro Ramírez ─────────────────────────────────────────────────────────────

class TestPedroRamirez:
    def test_coge_carta_del_descarte_si_acepta(self):
        io = FakeIO()
        io.queue("SI")
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Pedro Ramirez")
        carta_descarte = make_carta(idClase=13, nombre="Cerveza")
        juego.monton_descartes.append(carta_descarte)
        _set_hand(juego, 0)
        juego._fase_robo(0)
        assert carta_descarte in juego.jugadores[0].cartasMano
        assert len(juego.jugadores[0].cartasMano) == 2  # 1 del descarte + 1 del mazo

    def test_roba_del_mazo_si_rechaza_descarte(self):
        io = FakeIO()
        io.queue(False)  # FakeIO devuelve el valor raw; "NO" sería truthy como string
        juego = make_juego(num_jugadores=4, io=io)
        _personaje(juego, 0, "Pedro Ramirez")
        carta_descarte = make_carta(idClase=13, nombre="Cerveza")
        juego.monton_descartes.append(carta_descarte)
        _set_hand(juego, 0)
        juego._fase_robo(0)
        assert carta_descarte not in juego.jugadores[0].cartasMano
        assert len(juego.jugadores[0].cartasMano) == 2
