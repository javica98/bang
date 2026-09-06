"""Entorno Gymnasium para el bot RL (Fase 5) — el agente controla al
jugador 0 y decide tres cosas: qué carta jugar, a qué rival apuntar, y si
esquivar un Bang con Fallaste (ver rl_common.py para el diseño del
espacio de acción unificado). El resto de preguntas (elegir_personaje,
poder de Sid Ketchum, robos especiales...) las resuelve la heurística
interna, igual que en las fases anteriores — no todo vale la pena
metérselo al agente.

El motor (bang_game.py) es síncrono y no está pensado para "pausarse" a
mitad de partida, así que la partida corre en un hilo daemon y se
comunica con el hilo principal (Gym) por colas bloqueantes — el mismo
patrón que ya usa FlaskIO para pausar el hilo de juego y esperar al
cliente web, aquí esperando a step() en vez de a una petición HTTP.
"""
import builtins
import contextlib
import os
import queue
import sys
import threading

import gymnasium as gym
import numpy as np
from gymnasium import spaces

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bang_game import info_extract, create_players, Juego  # noqa: E402
from bot_ai import BotAI  # noqa: E402
from sim_io import SimIO  # noqa: E402
from rl_common import (  # noqa: E402
    N_OBS, N_ACCIONES, TIPO_CARTA, TIPO_JUGADOR, TIPO_ESQUIVAR, VOCABULARIO_CARTAS,
    observacion, accion_a_respuesta, gano_bando, potencial_vidas, es_prompt_esquivar,
)

CARTAS_CSV = os.path.join(BASE_DIR, "cartas.csv")
PERSONAJES_TXT = os.path.join(BASE_DIR, "personajes.txt")
ROLES_TXT = os.path.join(BASE_DIR, "roles.txt")

PENALIZACION_PASO = -0.002
ESCALA_SHAPING = 0.05  # peso del shaping por diferencia de vidas frente al +-1 terminal

EGO_ID = 0
_FIN = ("fin", None, None, None)


def _mano_de(jugador):
    return [
        {"nombre": c.nombre, "tipo": c.tipo, "idClase": c.idClase, "indice": i}
        for i, c in enumerate(jugador.cartasMano)
    ]


@contextlib.contextmanager
def _silenciar_print():
    orig = builtins.print
    builtins.print = lambda *a, **k: None
    try:
        yield
    finally:
        builtins.print = orig


class _EgoIO(SimIO):
    """SimIO normal para los rivales; para el ego (EGO_ID), en las tres
    preguntas que decide el RL, deposita la pregunta en una cola y
    bloquea esperando la respuesta que step() ponga en la otra cola. El
    resto de preguntas del ego (elegir_personaje, prompts que no son de
    esquivar...) van por el camino normal, resueltas por bots[0]
    (heurística), igual que ocurre para cualquier rival."""

    def __init__(self, bots, pregunta_q, respuesta_q, max_pasos=None, alcance_completo=True):
        super().__init__(bots, max_pasos=max_pasos)
        self._pregunta_q = pregunta_q
        self._respuesta_q = respuesta_q
        # Si es False, el agente vuelve al alcance original (solo "qué
        # carta jugar") — a quién apuntar y si esquivar los resuelve la
        # heurística, como en la primera versión de la Fase 5. Sirve para
        # aislar el efecto de las otras mejoras (red más grande, arranque
        # en caliente, shaping, pool priorizado) de la ampliación de
        # alcance, que en la comparación empeoró el resultado.
        self._alcance_completo = alcance_completo

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        if jugador.idJugador != EGO_ID:
            return super().elegir_carta(jugador, text, opciones, permitir_fin, permitir_poder)
        self.current_jugador = jugador
        self._asking_id = jugador.idJugador
        self.pasos += 1
        pregunta = {
            "texto": text, "opciones": list(opciones), "permitir_fin": permitir_fin,
            "permitir_poder": permitir_poder, "jugador_id": jugador.idJugador,
            "mano": _mano_de(jugador),
        }
        self._pregunta_q.put(("pregunta", TIPO_CARTA, pregunta, jugador))
        return self._respuesta_q.get()

    def elegir_jugador(self, jugadores, text, jugadores_fuera_alcance=None):
        if not self._alcance_completo or self._asking_id != EGO_ID:
            return super().elegir_jugador(jugadores, text, jugadores_fuera_alcance)
        jugador = self.current_jugador
        self.pasos += 1
        pregunta = {
            "texto": text,
            "jugadores_validos": [j.idJugador for j in jugadores],
            "jugadores_fuera_alcance": [j.idJugador for j in (jugadores_fuera_alcance or [])],
            "mano": _mano_de(jugador),
        }
        self._pregunta_q.put(("pregunta", TIPO_JUGADOR, pregunta, jugador))
        return self._respuesta_q.get()

    def prompt(self, text, options=None):
        if self.current_jugador is not None:
            self._asking_id = self.current_jugador.idJugador
        pregunta_bruta = {"texto": text, "opciones": options or []}
        if self._alcance_completo and self._asking_id == EGO_ID and es_prompt_esquivar(pregunta_bruta):
            jugador = self.current_jugador
            self.pasos += 1
            pregunta = dict(pregunta_bruta)
            pregunta["mano"] = _mano_de(jugador)
            self._pregunta_q.put(("pregunta", TIPO_ESQUIVAR, pregunta, jugador))
            return self._respuesta_q.get()
        return super().prompt(text, options)


class BangCardEnv(gym.Env):
    """Un episodio = una partida completa vista desde el jugador 0.
    Recompensa: +1/-1 al final según gane o pierda mi bando, más un
    shaping denso por diferencia de vidas y una pequeña penalización por
    paso (ver rl_common.potencial_vidas)."""

    metadata = {"render_modes": []}

    def __init__(self, oponente_sampler, num_players=4, max_pasos=3000, alcance_completo=True):
        super().__init__()
        self.oponente_sampler = oponente_sampler  # callable(bot_id) -> objeto tipo BotAI
        self.num_players = num_players
        self.max_pasos = max_pasos
        self.alcance_completo = alcance_completo
        self.observation_space = spaces.Box(low=-1e3, high=1e3, shape=(N_OBS,), dtype=np.float32)
        self.action_space = spaces.Discrete(N_ACCIONES)
        self._hilo = None
        self._pregunta_q = None
        self._respuesta_q = None
        self._pendiente = None  # (tipo, pregunta, jugador)
        self._mascara_actual = np.ones(N_ACCIONES, dtype=bool)
        self._juego = None
        # Solo hace falta para TIPO_CARTA: el enmascarado de cartas
        # comprueba que estén OFRECIDAS (por índice), no que el motor las
        # vaya a aceptar de verdad (p.ej. un 2º Bang superando el límite
        # del turno es "legal" según la máscara pero un no-op real). Sin
        # esto el agente puede quedarse pidiendo la misma jugada inválida
        # para siempre — es justo lo que pasó en el primer entrenamiento.
        # (TIPO_JUGADOR/TIPO_ESQUIVAR no lo necesitan: su máscara ya es
        # exactamente lo que el motor acepta, no hay casos "ofrecido pero
        # rechazado" para esos dos tipos.)
        #
        # Ojo: se guarda por separado de "el paso inmediatamente anterior"
        # porque ahora hay preguntas de otro tipo intercaladas (p.ej. Bang
        # -> elegir objetivo -> el motor rechaza el Bang por el límite de
        # turno -> vuelve a preguntar carta). Si solo comparara con el paso
        # previo, esa secuencia nunca se detectaría como fallo porque el
        # paso de "elegir objetivo" rompe la comparación consecutiva.
        self._ultimo_intento_carta = None  # (nombre, len(mano) antes de intentarlo)
        self._acciones_fallidas = set()
        self._mi_rol = None
        self._potencial_anterior = 0.0

    def _lanzar_partida(self):
        baraja, personajes, roles = info_extract(CARTAS_CSV, PERSONAJES_TXT, ROLES_TXT)
        nombres = [f"Bot{i}" for i in range(self.num_players)]
        # El ego (id 0) también necesita un bot heurístico: cubre todo lo
        # que no decide el RL (elegir_personaje al inicio, prompts que no
        # son de esquivar...) — _EgoIO intercepta el resto aparte.
        bots = {0: BotAI(0)}
        bots.update({i: self.oponente_sampler(i) for i in range(1, self.num_players)})
        self._pregunta_q = queue.Queue()
        self._respuesta_q = queue.Queue()
        io = _EgoIO(bots, self._pregunta_q, self._respuesta_q, max_pasos=self.max_pasos,
                    alcance_completo=self.alcance_completo)
        jugadores = create_players(self.num_players, nombres, personajes, roles, io=io)
        self._juego = Juego(jugadores, baraja, io=io)
        io.set_game(self._juego)

        def correr():
            with _silenciar_print():
                try:
                    self._juego.partida()
                except Exception:
                    pass
            self._pregunta_q.put(_FIN)

        self._hilo = threading.Thread(target=correr, daemon=True)
        self._hilo.start()

    def _observar_actual(self, tipo, pregunta, jugador):
        obs, mascara = observacion(tipo, pregunta, jugador, self._juego)
        if tipo == TIPO_CARTA and self._acciones_fallidas:
            mascara_filtrada = mascara.copy()
            for nombre in self._acciones_fallidas:
                idx = VOCABULARIO_CARTAS.index(nombre)
                mascara_filtrada[idx] = False
            if mascara_filtrada.any():
                mascara = mascara_filtrada
        return obs, mascara

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._lanzar_partida()
        self._ultimo_intento_carta = None
        self._acciones_fallidas = set()
        status, tipo, pregunta, jugador = self._pregunta_q.get()
        if status == "fin":
            # La partida terminó sin pedirle nada al ego (jugador 0 murió
            # por Dinamita antes de su 1er turno, caso raro) — reintenta.
            return self.reset(seed=seed, options=options)
        self._pendiente = (tipo, pregunta, jugador)
        obs, mascara = self._observar_actual(tipo, pregunta, jugador)
        self._mascara_actual = mascara
        self._ultimo_intento_carta = None
        self._mi_rol = jugador.rol
        self._potencial_anterior = potencial_vidas(self._juego, self._mi_rol)
        return obs, {}

    def step(self, action):
        tipo, pregunta, jugador = self._pendiente
        respuesta = accion_a_respuesta(tipo, int(action), pregunta, jugador, self._juego)
        self._respuesta_q.put(respuesta)

        if tipo == TIPO_CARTA:
            # Se guarda aquí (no se compara todavía) porque entre este
            # intento y la próxima pregunta de carta puede haber una
            # pregunta de OTRO tipo de por medio (elegir objetivo) — hay
            # que comparar contra "la última vez que se preguntó carta",
            # no contra "el paso inmediatamente anterior".
            self._ultimo_intento_carta = (VOCABULARIO_CARTAS[int(action)], len(pregunta["mano"]))

        status, tipo2, pregunta2, jugador2 = self._pregunta_q.get()
        terminado = status == "fin"
        if terminado:
            mi_rol_real = self._juego.jugadores[EGO_ID].rol
            if self._juego.ganador is None:
                # Partida cortada por max_pasos: NUNCA debe ser mejor que
                # perder limpiamente, o el agente aprende a alargar la
                # partida en vez de competir (esto pasó de verdad en el
                # primer entrenamiento: 90% de las partidas acababan en
                # timeout). Al menos tan malo como una derrota real.
                recompensa = -1.0
            else:
                recompensa = 1.0 if gano_bando(self._juego.ganador, mi_rol_real) else -1.0
            obs = np.zeros(N_OBS, dtype=np.float32)
            self._mascara_actual = np.ones(N_ACCIONES, dtype=bool)
        else:
            # ¿No-op de carta? Si la próxima pregunta vuelve a ser de carta
            # y la mano sigue teniendo el mismo tamaño que cuando se
            # intentó la última carta (aunque de por medio hubiera una
            # pregunta de objetivo/esquivar), el motor la rechazó sin hacer
            # nada -> excluirla la próxima vez.
            if tipo2 == TIPO_CARTA and self._ultimo_intento_carta is not None:
                nombre_prev, mano_len_antes = self._ultimo_intento_carta
                if len(pregunta2["mano"]) == mano_len_antes:
                    self._acciones_fallidas.add(nombre_prev)
                else:
                    self._acciones_fallidas.clear()
                self._ultimo_intento_carta = None

            # Shaping por potencial (Ng et al. 1999): recompensa densa por
            # cómo cambió la diferencia de vidas mi-bando/enemigo desde mi
            # última decisión — no cambia la política óptima, solo ayuda a
            # aprender más rápido que con el +-1 disperso del final solo.
            potencial_actual = potencial_vidas(self._juego, self._mi_rol)
            recompensa = PENALIZACION_PASO + ESCALA_SHAPING * (potencial_actual - self._potencial_anterior)
            self._potencial_anterior = potencial_actual
            self._pendiente = (tipo2, pregunta2, jugador2)
            obs, mascara = self._observar_actual(tipo2, pregunta2, jugador2)
            self._mascara_actual = mascara
        return obs, recompensa, terminado, False, {}

    def action_masks(self):
        return self._mascara_actual


def oponente_heuristico(bot_id):
    """Sampler por defecto: rivales heurísticos de Fase 1. Sirve para
    arrancar el pool de self-play antes de tener ningún checkpoint propio."""
    return BotAI(bot_id)
