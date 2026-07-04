from bang_game import DESCRIPCIONES_PERSONAJE


class FlaskIO:
    """IO adapter que pausa el hilo del juego y espera respuesta del cliente web.

    Actúa de puente entre el motor de juego (que corre en un hilo daemon) y el
    frontend web (que hace polling a /estado). Cada llamada a ``_ask()`` deposita
    una pregunta en ``question_q`` y bloquea el hilo hasta que el cliente envía
    la respuesta a /accion, que la coloca en ``answer_q``.

    Attributes:
        question_q (queue.Queue): Cola de preguntas hacia el cliente.
        answer_q (queue.Queue): Cola de respuestas del cliente.
        log (list): Lista compartida de mensajes de log visibles en el frontend.
        current_jugador (Jugador | None): Jugador cuya mano se muestra actualmente.
        juego (Juego | None): Referencia al objeto Juego activo.
    """

    def __init__(self, question_q, answer_q, log_list):
        self.question_q = question_q
        self.answer_q = answer_q
        self.log = log_list
        self.current_jugador = None
        self.juego = None

    def set_game(self, juego):
        """Guarda la referencia al objeto Juego para que los métodos puedan consultarlo."""
        self.juego = juego

    def _ask(self, pregunta: dict):
        """Envía una pregunta al cliente y bloquea hasta recibir respuesta."""
        self.question_q.put(pregunta)
        return self.answer_q.get()

    # ------------------------------------------------------------------ genérico
    def prompt(self, text, options=None):
        """Muestra un mensaje genérico al jugador y devuelve su respuesta en texto libre."""
        return self._ask({
            "tipo": "prompt",
            "texto": text,
            "opciones": options or [],
        })

    # ------------------------------------------------------------------ setup
    def elegir_personaje(self, nombre_jugador, rol, personaje_a, personaje_b):
        """Presenta al jugador dos personajes y devuelve el elegido.

        Returns:
            Personaje: El personaje seleccionado (A o B).
        """
        resp = self._ask({
            "tipo": "elegir_personaje",
            "nombre_jugador": nombre_jugador,
            "rol": rol,
            "personaje_a": {
                "nombre": personaje_a.nombre,
                "vidas": personaje_a.vidas,
                "desc": DESCRIPCIONES_PERSONAJE.get(personaje_a.nombre, ""),
            },
            "personaje_b": {
                "nombre": personaje_b.nombre,
                "vidas": personaje_b.vidas,
                "desc": DESCRIPCIONES_PERSONAJE.get(personaje_b.nombre, ""),
            },
        })
        return personaje_a if resp == "A" else personaje_b

    # ------------------------------------------------------------------ turno
    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        """Permite al jugador activo elegir una carta de su mano, finalizar el turno o usar su poder.

        Actualiza ``current_jugador`` para que /estado pueda exponer la mano correcta.

        Returns:
            str: Índice de carta (base 1), "FIN" o "PODER".
        """
        self.current_jugador = jugador
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
        """Muestra la mesa y pide elegir un jugador objetivo.

        Returns:
            int | None: idJugador del rival seleccionado, o None si se cancela.
        """
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
        """Pide elegir una carta (de mano o equipada) del rival indicado.

        Returns:
            tuple[str, int]: (``"mano"`` | ``"equipada"``, índice).
        """
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
    def elegir_lucky_duke(self, jugador, carta1, carta2):
        """Lucky Duke: muestra las 2 cartas robadas y devuelve la elegida para el chequeo.

        Returns:
            Carta: La carta seleccionada.
        """
        resp = self._ask({
            "tipo": "elegir_lucky_duke",
            "jugador_id": jugador.idJugador,
            "carta1": {"nombre": carta1.nombre, "palo": carta1.palo, "numero": carta1.numero},
            "carta2": {"nombre": carta2.nombre, "palo": carta2.palo, "numero": carta2.numero},
        })
        return carta1 if resp == "0" else carta2

    def elegir_robo_jesse(self, jugador, rivales):
        """Jesse Jones: pregunta si robar a un rival o al mazo, y cuál rival elegir.

        Returns:
            int | None: idJugador del rival del que robar, o None para robar del mazo.
        """
        resp = self._ask({
            "tipo": "elegir_robo_jesse",
            "jugador_id": jugador.idJugador,
            "rivales": [j.idJugador for j in rivales],
        })
        if resp in (None, "None", "null"):
            return None
        return int(resp)

    def elegir_robo_pedro(self, jugador, carta_top):
        """Pedro Ramírez: ofrece coger la carta superior del descarte o robar del mazo.

        Returns:
            bool: True si elige coger del descarte.
        """
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
        """Kit Carlson: muestra 3 cartas y devuelve el índice de la que se devuelve al mazo.

        Returns:
            int: Índice (0-2) de la carta a devolver.
        """
        resp = self._ask({
            "tipo": "elegir_kit_carlson",
            "jugador_id": jugador.idJugador,
            "cartas": [
                {"nombre": c.nombre, "palo": c.palo, "numero": c.numero}
                for c in cartas
            ],
        })
        return int(resp)

    def elegir_almacen_carta(self, jugador, cartas):
        """Almacén: el jugador elige qué carta tomar de las expuestas en la mesa.

        Returns:
            int: Índice de la carta elegida dentro de ``cartas``.
        """
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
        """Notifica al frontend que la partida ha terminado y quién ha ganado."""
        self._ask({
            "tipo": "game_over",
            "ganador": ganador,
        })
