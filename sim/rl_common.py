"""Utilidades compartidas entre el entorno Gym (rl_env.py) y el bot RL de
evaluación (rl_bot.py) — Fase 5 del roadmap de IA.

v2: el agente decide tres tipos de cosas (antes solo "qué carta jugar"):
  - qué carta jugar (o FIN/PODER)              -> índices [0, N_CARTAS)
  - a qué rival apuntar (Bang/Duelo/Cárcel...)  -> índices [N_CARTAS, N_CARTAS+N_RIVALES)
  - si esquivar un Bang con Fallaste (SI/NO)    -> los 2 últimos índices
Todo cabe en un único Discrete(N_ACCIONES) para poder seguir usando
MaskablePPO tal cual: la observación lleva un one-hot de qué tipo de
pregunta es esta vez, y la máscara solo deja activo el tramo que toca.
El resto de preguntas (elegir_personaje, robos especiales, el resto de
prompts como el poder de Sid Ketchum...) se siguen delegando al BotAI
heurístico interno — no todo vale la pena metrelo en el espacio de acción.
"""
import os
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from features import features_estado, VOCABULARIO_CARTAS, nombre_de_opcion, NOMBRES_FEATURES, NUM_RIVALES  # noqa: E402

ESTADO_COLS = [c for c in NOMBRES_FEATURES if not c.startswith("carta_") and c != "prioridad_base"]
N_ESTADO = len(ESTADO_COLS)

TIPO_CARTA = "elegir_carta"
TIPO_JUGADOR = "elegir_jugador"
TIPO_ESQUIVAR = "prompt_esquivar"
TIPOS = [TIPO_CARTA, TIPO_JUGADOR, TIPO_ESQUIVAR]
N_TIPOS = len(TIPOS)

N_CARTAS = len(VOCABULARIO_CARTAS)
N_RIVALES_ACCION = NUM_RIVALES
N_ESQUIVAR = 2

OFFSET_CARTA = 0
OFFSET_JUGADOR = N_CARTAS
OFFSET_ESQUIVAR = N_CARTAS + N_RIVALES_ACCION
N_ACCIONES = N_CARTAS + N_RIVALES_ACCION + N_ESQUIVAR

N_OBS = N_ESTADO + N_TIPOS + N_ACCIONES


# ------------------------------------------------------------------ elegir_carta

def opciones_con_fin_poder(pregunta):
    opciones = list(pregunta["opciones"])
    if pregunta.get("permitir_fin", True):
        opciones.append("FIN")
    if pregunta.get("permitir_poder", False):
        opciones.append("PODER")
    return opciones


def _mascara_carta(pregunta):
    mano = pregunta["mano"]
    nombres_legales = set()
    for op in opciones_con_fin_poder(pregunta):
        n = nombre_de_opcion(op, mano)
        if n is not None:
            nombres_legales.add(n)
    return np.array([1.0 if n in nombres_legales else 0.0 for n in VOCABULARIO_CARTAS], dtype=np.float32)


def _accion_a_opcion_carta(accion_local, pregunta):
    nombre = VOCABULARIO_CARTAS[accion_local]
    mano = pregunta["mano"]
    opciones = opciones_con_fin_poder(pregunta)
    for op in opciones:
        if nombre_de_opcion(op, mano) == nombre:
            return op
    return "FIN" if "FIN" in opciones else opciones[0]


# ------------------------------------------------------------------ elegir_jugador (a quién apuntar)

def offset_relativo(mi_id, rival_id, n):
    """1..n-1: cuántos puestos por delante de mí (en orden de turno) está
    rival_id — mismo criterio que features._rivales_en_orden_de_turno."""
    return (rival_id - mi_id) % n


def _mascara_jugador(pregunta, jugador, juego):
    n = len(juego.jugadores)
    validos = set(pregunta.get("jugadores_validos", []))
    m = np.zeros(N_RIVALES_ACCION, dtype=np.float32)
    for rival_id in validos:
        offset = offset_relativo(jugador.idJugador, rival_id, n)
        if 1 <= offset <= N_RIVALES_ACCION:
            m[offset - 1] = 1.0
    return m


def _accion_a_id_jugador(accion_local, pregunta, jugador, juego):
    n = len(juego.jugadores)
    offset = accion_local + 1
    rival_id = (jugador.idJugador + offset) % n
    validos = pregunta.get("jugadores_validos", [])
    if rival_id in validos:
        return rival_id
    return validos[0] if validos else None


# ------------------------------------------------------------------ prompt (esquivar Bang)

def es_prompt_esquivar(pregunta):
    """¿Es esta pregunta 'prompt' concretamente la de esquivar un Bang con
    Fallaste? (mismas palabras clave que usa BotAI._responder_prompt para
    reconocerla). El resto de prompts (poder de Sid Ketchum, descartes...)
    NO entran en el espacio de acción del RL, se delegan a la heurística."""
    texto = pregunta.get("texto", "").lower()
    opciones = set(pregunta.get("opciones", []))
    palabras_clave = "te han atacado" in texto or "fallaste" in texto or "bang" in texto
    return palabras_clave and opciones == {"SI", "NO"}


def _mascara_esquivar(pregunta):
    opciones = set(pregunta.get("opciones", []))
    return np.array([
        1.0 if "SI" in opciones else 0.0,
        1.0 if "NO" in opciones else 0.0,
    ], dtype=np.float32)


def _accion_a_si_no(accion_local):
    return "SI" if accion_local == 0 else "NO"


# ------------------------------------------------------------------ API unificada

def mascara_por_tipo(tipo, pregunta, jugador, juego):
    m = np.zeros(N_ACCIONES, dtype=np.float32)
    if tipo == TIPO_CARTA:
        m[OFFSET_CARTA:OFFSET_CARTA + N_CARTAS] = _mascara_carta(pregunta)
    elif tipo == TIPO_JUGADOR:
        m[OFFSET_JUGADOR:OFFSET_JUGADOR + N_RIVALES_ACCION] = _mascara_jugador(pregunta, jugador, juego)
    elif tipo == TIPO_ESQUIVAR:
        m[OFFSET_ESQUIVAR:OFFSET_ESQUIVAR + N_ESQUIVAR] = _mascara_esquivar(pregunta)
    else:
        raise ValueError(f"tipo desconocido: {tipo!r}")
    return m


def observacion(tipo, pregunta, jugador, juego):
    """(vector_obs, mascara_bool) — incluye qué tipo de pregunta es esta
    vez (one-hot) además del estado y la máscara de acciones legales."""
    estado = features_estado(pregunta, jugador, juego)
    vec_estado = np.array([estado[c] for c in ESTADO_COLS], dtype=np.float32)
    vec_tipo = np.array([1.0 if tipo == t else 0.0 for t in TIPOS], dtype=np.float32)
    mascara = mascara_por_tipo(tipo, pregunta, jugador, juego)
    obs = np.concatenate([vec_estado, vec_tipo, mascara]).astype(np.float32)
    return obs, mascara.astype(bool)


def accion_a_respuesta(tipo, accion_idx, pregunta, jugador, juego):
    """Traduce un índice de acción (0..N_ACCIONES-1) a la respuesta real
    que espera el motor de juego para este tipo de pregunta."""
    if tipo == TIPO_CARTA:
        return _accion_a_opcion_carta(accion_idx - OFFSET_CARTA, pregunta)
    if tipo == TIPO_JUGADOR:
        return _accion_a_id_jugador(accion_idx - OFFSET_JUGADOR, pregunta, jugador, juego)
    if tipo == TIPO_ESQUIVAR:
        return _accion_a_si_no(accion_idx - OFFSET_ESQUIVAR)
    raise ValueError(f"tipo desconocido: {tipo!r}")


def gano_bando(ganador, mi_rol_real):
    if mi_rol_real in ("Sheriff", "Ayudante"):
        return ganador == "Sheriff"
    if mi_rol_real == "Forajido":
        return ganador == "Forajidos"
    if mi_rol_real == "Renegado":
        return ganador == "Renegado"
    return False


_ROLES_BANDO = {
    "Sheriff": ({"Sheriff", "Ayudante"}, {"Forajido"}),
    "Ayudante": ({"Sheriff", "Ayudante"}, {"Forajido"}),
    "Forajido": ({"Forajido"}, {"Sheriff", "Ayudante"}),
    "Renegado": ({"Renegado"}, {"Sheriff", "Ayudante", "Forajido"}),
}


def potencial_vidas(juego, mi_rol_real):
    """vidas de mi bando menos vidas del bando enemigo (el Renegado no
    tiene aliados, solo enemigos). Función de potencial para reward
    shaping: la diferencia entre dos llamadas da una señal densa de
    "¿mejoró o empeoró mi situación?" sin alterar la política óptima
    (shaping basado en potencial, Ng et al. 1999) — coherente con la
    recompensa dispersa +1/-1 al final de la partida.
    """
    aliados, enemigos = _ROLES_BANDO.get(mi_rol_real, (set(), set()))
    vidas_aliados = sum(j.vidas for j in juego.jugadores if j.rol in aliados)
    vidas_enemigos = sum(j.vidas for j in juego.jugadores if j.rol in enemigos)
    return float(vidas_aliados - vidas_enemigos)
