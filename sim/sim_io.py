"""SimIO: adaptador IO headless para simulaciones masivas de BANG! (Fase 0).

Todos los jugadores son bots (BotAI); a diferencia de FlaskIO no hay colas,
time.sleep() de animación, ni emisión de eventos — cada pregunta se resuelve
llamando directamente a bot.decidir() en el mismo hilo. Se conecta a Juego
exactamente igual que ConsoleIO o FlaskIO (Juego(..., io=SimIO(...))).
"""


class PasosExcedidos(Exception):
    """Se lanza cuando una partida supera max_pasos, para cortar bots en bucle."""

    def __init__(self, pasos):
        super().__init__(f"Partida excedió {pasos} pasos sin terminar")
        self.pasos = pasos


class SimIO:
    def __init__(self, bots, debug=False, max_pasos=None):
        self.bots = bots
        self.debug = debug
        self.max_pasos = max_pasos
        self.current_jugador = None
        self.juego = None
        self._asking_id = None
        self._setup_idx = 0
        self.pasos = 0

    def set_game(self, juego):
        self.juego = juego

    def _ask(self, pregunta):
        self.pasos += 1
        if self.max_pasos is not None and self.pasos > self.max_pasos:
            raise PasosExcedidos(self.pasos)
        jugador = self.current_jugador
        resp = self.bots[self._asking_id].decidir(pregunta, jugador, self.juego)
        if self.debug:
            nombre = jugador.nombre if jugador else f"Bot{self._asking_id}"
            msg = f"BOT {nombre} [{pregunta.get('tipo', '?')}] -> {resp}"
            try:
                print(msg)
            except UnicodeEncodeError:
                print(msg.encode('ascii', errors='replace').decode('ascii'))
        return str(resp) if resp is not None else 'None'

    # ------------------------------------------------------------------ genérico
    def prompt(self, text, options=None):
        if self.current_jugador is not None:
            self._asking_id = self.current_jugador.idJugador
        return self._ask({
            "tipo": "prompt",
            "texto": text,
            "opciones": options or [],
        })

    # ------------------------------------------------------------------ setup
    def elegir_personaje(self, nombre_jugador, rol, personaje_a, personaje_b):
        self._asking_id = self._setup_idx
        self._setup_idx += 1
        resp = self._ask({
            "tipo": "elegir_personaje",
            "nombre_jugador": nombre_jugador,
            "rol": rol,
            "personaje_a": {"nombre": personaje_a.nombre, "vidas": personaje_a.vidas},
            "personaje_b": {"nombre": personaje_b.nombre, "vidas": personaje_b.vidas},
        })
        return personaje_a if resp == "A" else personaje_b

    # ------------------------------------------------------------------ turno
    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        self.current_jugador = jugador
        self._asking_id = jugador.idJugador
        return self._ask({
            "tipo": "elegir_carta",
            "texto": text,
            "opciones": list(opciones),
            "permitir_fin": permitir_fin,
            "permitir_poder": permitir_poder,
            "jugador_id": jugador.idJugador,
            "mano": [
                {"nombre": c.nombre, "tipo": c.tipo, "idClase": c.idClase, "indice": i}
                for i, c in enumerate(jugador.cartasMano)
            ],
        })

    def elegir_jugador(self, jugadores, text, jugadores_fuera_alcance=None):
        resp = self._ask({
            "tipo": "elegir_jugador",
            "texto": text,
            "jugadores_validos": [j.idJugador for j in jugadores],
            "jugadores_fuera_alcance": [j.idJugador for j in (jugadores_fuera_alcance or [])],
        })
        if resp in (None, "None", "null"):
            return None
        return int(resp)

    def elegir_carta_rival(self, rival, text):
        self.current_jugador = rival
        resp = self._ask({
            "tipo": "elegir_carta_rival",
            "texto": text,
            "rival_id": rival.idJugador,
            "mano_size": len(rival.cartasMano),
            "equipadas": [
                {"nombre": c.nombre, "indice": i}
                for i, c in enumerate(rival.cartasEquipadas)
            ],
        })
        origen, indice = resp.split(":")
        return (origen, int(indice))

    # ------------------------------------------------------------------ personajes
    def observar(self, señal, actor_id):
        for bot in self.bots.values():
            bot.observar(señal, actor_id)

    def elegir_lucky_duke(self, jugador, carta1, carta2):
        self._asking_id = jugador.idJugador
        resp = self._ask({
            "tipo": "elegir_lucky_duke",
            "jugador_id": jugador.idJugador,
            "carta1": {"nombre": carta1.nombre, "palo": carta1.palo, "numero": carta1.numero},
            "carta2": {"nombre": carta2.nombre, "palo": carta2.palo, "numero": carta2.numero},
        })
        return carta1 if resp == "0" else carta2

    def elegir_robo_jesse(self, jugador, rivales):
        self._asking_id = jugador.idJugador
        resp = self._ask({
            "tipo": "elegir_robo_jesse",
            "jugador_id": jugador.idJugador,
            "rivales": [j.idJugador for j in rivales],
        })
        if resp in (None, "None", "null"):
            return None
        return int(resp)

    def elegir_robo_pedro(self, jugador, carta_top):
        self._asking_id = jugador.idJugador
        self.current_jugador = jugador
        resp = self._ask({
            "tipo": "elegir_robo_pedro",
            "jugador_id": jugador.idJugador,
            "carta_top": {
                "nombre": carta_top.nombre,
                "palo": carta_top.palo,
                "numero": carta_top.numero,
            },
        })
        return resp == "SI"

    def elegir_kit_carlson(self, jugador, cartas):
        self._asking_id = jugador.idJugador
        resp = self._ask({
            "tipo": "elegir_kit_carlson",
            "jugador_id": jugador.idJugador,
            "cartas": [
                {"nombre": c.nombre, "palo": c.palo, "numero": c.numero}
                for c in cartas
            ],
        })
        try:
            return int(resp)
        except (ValueError, TypeError):
            return 0

    def elegir_almacen_carta(self, jugador, cartas):
        self._asking_id = jugador.idJugador
        resp = self._ask({
            "tipo": "elegir_almacen_carta",
            "jugador_id": jugador.idJugador,
            "cartas": [
                {"nombre": c.nombre, "palo": c.palo, "numero": c.numero}
                for c in cartas
            ],
        })
        return int(resp)

    # ------------------------------------------------------------------ fin
    def mostrar_game_over(self, ganador):
        pass
