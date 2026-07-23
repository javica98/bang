"""Tests for Juego.distancia(): the asymmetric, circular-table distance calculation
used to decide whether a weapon/Bang is in range. See bang_game.py's docstring on
Juego.distancia for the base algorithm (min steps around a circle of *alive* players)
and the two asymmetric modifiers (Mira Telescopica/Rose Doolan on the attacker,
Mustang/Paul Regret on the target).
"""


class TestDistanciaBase:
    def test_distancia_a_uno_mismo_es_cero(self, juego_factory):
        juego = juego_factory(num_jugadores=4)
        assert juego.distancia(0, 0) == 0

    def test_jugadores_adyacentes_estan_a_distancia_uno(self, juego_factory):
        juego = juego_factory(num_jugadores=4)
        assert juego.distancia(0, 1) == 1
        assert juego.distancia(1, 0) == 1

    def test_jugadores_opuestos_en_mesa_de_cuatro(self, juego_factory):
        juego = juego_factory(num_jugadores=4)
        assert juego.distancia(0, 2) == 2

    def test_la_distancia_da_la_vuelta_a_la_mesa(self, juego_factory):
        # En una mesa de 7, los jugadores 0 y 6 son vecinos por el otro lado.
        juego = juego_factory(num_jugadores=7)
        assert juego.distancia(0, 6) == 1

    def test_distancia_maxima_en_mesa_de_siete(self, juego_factory):
        juego = juego_factory(num_jugadores=7)
        assert juego.distancia(0, 3) == 3
        assert juego.distancia(0, 4) == 3


class TestDistanciaConJugadoresMuertos:
    def test_jugador_muerto_entre_medias_reduce_la_distancia(self, juego_factory):
        juego = juego_factory(num_jugadores=5)
        # Sin muertes: 0 -> 2 son 2 pasos.
        assert juego.distancia(0, 2) == 2

        juego.jugadores[1].muerto = True
        # Con el jugador 1 (que estaba en medio) muerto, 0 y 2 quedan a 1 paso.
        assert juego.distancia(0, 2) == 1

    def test_jugador_muerto_no_afecta_si_no_esta_entre_medias(self, juego_factory):
        juego = juego_factory(num_jugadores=5)
        juego.jugadores[3].muerto = True
        assert juego.distancia(0, 1) == 1


class TestDistanciaModificadorAtacante:
    def test_mira_telescopica_reduce_distancia_propia_en_uno(self, juego_factory):
        juego = juego_factory(num_jugadores=5)
        assert juego.distancia(0, 2) == 2
        juego.jugadores[0].miraTelescopica = True
        assert juego.distancia(0, 2) == 1

    def test_rose_doolan_reduce_distancia_propia_en_uno(self, juego_factory, personaje_factory):
        juego = juego_factory(num_jugadores=5)
        juego.jugadores[0].personaje = personaje_factory(nombre="Rose Doolan")
        assert juego.distancia(0, 2) == 1

    def test_modificador_de_atacante_no_baja_de_uno(self, juego_factory):
        juego = juego_factory(num_jugadores=4)
        juego.jugadores[0].miraTelescopica = True
        # Base ya es 1 (adyacentes); con -1 debería quedar en 0 pero se limita a 1.
        assert juego.distancia(0, 1) == 1


class TestDistanciaModificadorObjetivo:
    def test_mustang_del_objetivo_aumenta_distancia_en_uno(self, juego_factory):
        juego = juego_factory(num_jugadores=5)
        assert juego.distancia(0, 2) == 2
        juego.jugadores[2].mustang = True
        assert juego.distancia(0, 2) == 3

    def test_paul_regret_aumenta_distancia_en_uno(self, juego_factory, personaje_factory):
        juego = juego_factory(num_jugadores=5)
        juego.jugadores[2].personaje = personaje_factory(nombre="Paul Regret")
        assert juego.distancia(0, 2) == 3


class TestDistanciaModificadoresCombinados:
    def test_mira_telescopica_y_mustang_se_cancelan(self, juego_factory):
        juego = juego_factory(num_jugadores=5)
        juego.jugadores[0].miraTelescopica = True
        juego.jugadores[2].mustang = True
        assert juego.distancia(0, 2) == 2
