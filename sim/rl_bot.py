"""Bot RL (Fase 5) — envuelve un modelo MaskablePPO ya entrenado con la
misma interfaz que BotAI/MCTSBotAI/LLMBotAI/DLBotAI. Decide tres cosas
(ver rl_common.py): qué carta jugar, a quién apuntar, y si esquivar un
Bang — el resto de preguntas se delegan a la heurística interna.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bot_ai import BotAI  # noqa: E402
from rl_common import (  # noqa: E402
    TIPO_CARTA, TIPO_JUGADOR, TIPO_ESQUIVAR, VOCABULARIO_CARTAS,
    observacion, accion_a_respuesta, es_prompt_esquivar,
)


class RLBotAI:
    def __init__(self, bot_id, modelo, deterministico=False):
        """`modelo`: instancia ya cargada de sb3_contrib.MaskablePPO (o
        ruta a un .zip, en cuyo caso se carga aquí)."""
        self.bot_id = bot_id
        self._heuristico = BotAI(bot_id)
        if isinstance(modelo, str):
            from sb3_contrib import MaskablePPO
            modelo = MaskablePPO.load(modelo)
        self._modelo = modelo
        self._deterministico = deterministico
        # Solo hace falta para las decisiones de carta: el enmascarado
        # sabe qué cartas están OFRECIDAS, no si el motor las va a
        # aceptar de verdad (p.ej. un 2º Bang superando el límite del
        # turno) — sin esto el agente puede quedarse pidiendo la misma
        # jugada inválida para siempre. Los otros dos tipos de decisión
        # no lo necesitan: su máscara ya es justo lo que el motor acepta.
        self._ultima_eleccion = None
        self._acciones_fallidas = set()

    def observar(self, señal, actor_id):
        self._heuristico.observar(señal, actor_id)

    def decidir(self, pregunta, jugador, juego):
        if juego is not None:
            self._heuristico._inicializar(juego)
        tipo_pregunta = pregunta.get("tipo")
        if tipo_pregunta == "elegir_carta":
            return self._decidir_rl(TIPO_CARTA, pregunta, jugador, juego)
        if tipo_pregunta == "elegir_jugador":
            return self._decidir_rl(TIPO_JUGADOR, pregunta, jugador, juego)
        if tipo_pregunta == "prompt" and es_prompt_esquivar(pregunta):
            return self._decidir_rl(TIPO_ESQUIVAR, pregunta, jugador, juego)
        return self._heuristico.decidir(pregunta, jugador, juego)

    def _decidir_rl(self, tipo, pregunta, jugador, juego):
        mano = pregunta.get("mano", [])
        if tipo == TIPO_CARTA:
            if self._ultima_eleccion is not None:
                prev_nombre, prev_len = self._ultima_eleccion
                if prev_len == len(mano):
                    self._acciones_fallidas.add(prev_nombre)
                else:
                    self._acciones_fallidas.clear()
                self._ultima_eleccion = None
            else:
                self._acciones_fallidas.clear()

        obs, mask = observacion(tipo, pregunta, jugador, juego)
        if tipo == TIPO_CARTA and self._acciones_fallidas:
            mask_filtrada = mask.copy()
            for nombre in self._acciones_fallidas:
                mask_filtrada[VOCABULARIO_CARTAS.index(nombre)] = False
            if mask_filtrada.any():
                mask = mask_filtrada

        accion, _ = self._modelo.predict(obs, action_masks=mask, deterministic=self._deterministico)
        accion = int(accion)
        respuesta = accion_a_respuesta(tipo, accion, pregunta, jugador, juego)

        if tipo == TIPO_CARTA:
            self._ultima_eleccion = (VOCABULARIO_CARTAS[accion], len(mano))
        return respuesta
