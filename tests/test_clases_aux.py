import pytest

from ClasesAux import Carta, Personaje, Jugador


class TestPersonaje:
    def test_stores_fields(self):
        p = Personaje(3, "Willy the Kid", 4)
        assert p.idPersonaje == 3
        assert p.nombre == "Willy the Kid"
        assert p.vidas == 4


class TestCarta:
    def test_stores_fields_and_defaults_palo_numero_to_none(self):
        c = Carta(1, 11, "Bang", "Efecto")
        assert c.idObjeto == 1
        assert c.idClase == 11
        assert c.nombre == "Bang"
        assert c.tipo == "Efecto"
        assert c.numero is None
        assert c.palo is None


class TestJugadorVidas:
    def test_ayudante_uses_personaje_vidas_as_is(self, personaje_factory, jugador_factory):
        personaje = personaje_factory(vidas=4)
        jugador = jugador_factory(0, rol="Ayudante", personaje=personaje)
        assert jugador.vidas == 4
        assert jugador.vidasMax == 4

    def test_sheriff_gets_one_extra_life(self, personaje_factory, jugador_factory):
        personaje = personaje_factory(vidas=4)
        jugador = jugador_factory(0, rol="Sheriff", personaje=personaje)
        assert jugador.vidas == 5
        assert jugador.vidasMax == 5

    def test_perder_vida_decrements(self, jugador_factory):
        jugador = jugador_factory(0)
        vidas_antes = jugador.vidas
        jugador.perderVida()
        assert jugador.vidas == vidas_antes - 1
        assert jugador.muerto is False

    def test_perder_vida_marca_muerto_al_llegar_a_cero(self, personaje_factory, jugador_factory):
        jugador = jugador_factory(0, personaje=personaje_factory(vidas=1))
        jugador.perderVida()
        assert jugador.vidas == 0
        assert jugador.muerto is True

    def test_perder_vida_no_baja_de_cero(self, personaje_factory, jugador_factory):
        jugador = jugador_factory(0, personaje=personaje_factory(vidas=1))
        jugador.perderVida()
        jugador.perderVida()
        assert jugador.vidas == 0

    def test_ganar_vida_incrementa(self, personaje_factory, jugador_factory):
        jugador = jugador_factory(0, personaje=personaje_factory(vidas=4))
        jugador.perderVida()
        jugador.ganarVida()
        assert jugador.vidas == 4

    def test_ganar_vida_no_supera_max(self, jugador_factory):
        jugador = jugador_factory(0)
        jugador.ganarVida()
        assert jugador.vidas == jugador.vidasMax


class TestJugadorMano:
    def test_recibe_carta_la_anade_al_final(self, jugador_factory, carta_factory):
        jugador = jugador_factory(0)
        c1, c2 = carta_factory(), carta_factory()
        jugador.recibeCarta(c1)
        jugador.recibeCarta(c2)
        assert jugador.cartasMano == [c1, c2]

    def test_get_carta_no_la_retira(self, jugador_factory, carta_factory):
        jugador = jugador_factory(0)
        carta = carta_factory()
        jugador.recibeCarta(carta)
        assert jugador.getCarta(0) is carta
        assert jugador.cartasMano == [carta]

    def test_pierde_carta_la_retira(self, jugador_factory, carta_factory):
        jugador = jugador_factory(0)
        jugador.recibeCarta(carta_factory())
        jugador.pierdeCarta(0)
        assert jugador.cartasMano == []

    @pytest.mark.parametrize("indice", [-1, 0, 1])
    def test_get_carta_indice_invalido_lanza_index_error(self, jugador_factory, indice):
        jugador = jugador_factory(0)
        with pytest.raises(IndexError):
            jugador.getCarta(indice)

    def test_pierde_carta_indice_invalido_lanza_index_error(self, jugador_factory, carta_factory):
        jugador = jugador_factory(0)
        jugador.recibeCarta(carta_factory())
        with pytest.raises(IndexError):
            jugador.pierdeCarta(5)


class TestJugadorEquipo:
    def test_equipa_y_pierde_carta_equipada(self, jugador_factory, carta_factory):
        jugador = jugador_factory(0)
        carta = carta_factory(idClase=7, nombre="Mustang")
        jugador.equipaCarta(carta)
        assert jugador.cartasEquipadas == [carta]
        assert jugador.pierdeCartaEquipada(0) is carta
        assert jugador.cartasEquipadas == []

    def test_cambio_arma_actualiza_arma_y_distancia(self, jugador_factory):
        jugador = jugador_factory(0)
        jugador.cambioArma(3, 3)
        assert jugador.arma == 3
        assert jugador.distancia == 3

    @pytest.mark.parametrize(
        "poner, quitar, atributo",
        [
            ("ponerCarcel", "quitarCarcel", "carcel"),
            ("ponerMustang", "quitarMustang", "mustang"),
            ("ponerBarril", "quitarBarril", "barril"),
            ("ponerDinamita", "quitarDinamita", "dinamita"),
            ("ponerMiraTelescopica", "quitarMiraTelescopica", "miraTelescopica"),
            ("ponerVolcanic", "quitarVolcanic", "volcanic"),
        ],
    )
    def test_flags_de_estado_se_activan_y_desactivan(self, jugador_factory, poner, quitar, atributo):
        jugador = jugador_factory(0)
        assert getattr(jugador, atributo) is False
        getattr(jugador, poner)()
        assert getattr(jugador, atributo) is True
        getattr(jugador, quitar)()
        assert getattr(jugador, atributo) is False

    def test_poner_volcanic_fija_distancia_a_uno(self, jugador_factory):
        jugador = jugador_factory(0)
        jugador.cambioArma(5, 5)
        jugador.ponerVolcanic()
        assert jugador.distancia == 1


class TestJugadorMisc:
    def test_nombre_personaje_devuelve_nombre_del_personaje(self, personaje_factory, jugador_factory):
        personaje = personaje_factory(nombre="Lucky Duke")
        jugador = jugador_factory(0, personaje=personaje)
        assert jugador.nombre_personaje == "Lucky Duke"
