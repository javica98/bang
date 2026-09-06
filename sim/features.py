"""Featurización de decisiones "qué carta jugar" — Fase 4 (DL supervisado).

El problema se reformula como clasificación binaria por candidata: cada
decisión real (una mano concreta, unas opciones concretas) genera una fila
por cada carta candidata legal (incluyendo FIN/PODER), con label=1 para la
que el experto (heurística de Fase 1) realmente eligió y 0 para el resto.
Así se evita el problema de que "índice 2" no signifique lo mismo en manos
distintas — la identidad de la candidata (nombre de carta / FIN / PODER)
es la unidad de comparación, no su posición en la mano.

Los rivales se ordenan por posición RELATIVA de turno respecto al jugador
que decide (el siguiente en jugar = rival 1, etc.), no por idJugador
absoluto, para que el vector de features no dependa de qué asiento tiene
el bot en la mesa. Pensado para mesas de 4 jugadores (3 rivales fijos);
mesas de otro tamaño necesitarían ajustar NUM_RIVALES.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
for _p in (BASE_DIR, WEB_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bot_ai import PRIORIDAD_CARTA  # noqa: E402

NUM_RIVALES = 3

# Vocabulario cerrado de identidades de acción: las 22 cartas de cartas.csv
# (nombres reales, sin tilde/abreviar) + FIN + PODER.
VOCABULARIO_CARTAS = [
    "Volcanic", "Schofield", "Remington", "Caravina Revolver", "Winchester",
    "Carcel", "Mustang", "Barril", "Dinamita", "Mira Telescopica",
    "Bang", "Fallaste", "Cerveza", "Indios", "Duelo", "Ametralladora Gatling",
    "Panico", "Ingenua Explosiva", "Saloon", "Almacen", "Diligencia", "Wells Fargo",
    "FIN", "PODER",
]
_INDICE_CARTA = {nombre: i for i, nombre in enumerate(VOCABULARIO_CARTAS)}

ROLES = ["Sheriff", "Ayudante", "Forajido", "Renegado"]

EQUIPABLES_RIVAL = ["Barril", "Mustang", "Mira Telescopica", "Dinamita", "Carcel"]

NOMBRES_FEATURES = (
    [f"mi_rol_{r}" for r in ROLES]
    + ["mis_vidas_ratio", "mi_alcance", "ronda", "tam_mano", "rivales_vivos"]
    + [
        f"rival{k}_{campo}"
        for k in range(1, NUM_RIVALES + 1)
        for campo in (["vidas_ratio", "muerto", "es_sheriff", "distancia"] + EQUIPABLES_RIVAL)
    ]
    + [f"carta_{n}" for n in VOCABULARIO_CARTAS]
    + ["prioridad_base"]
)


def _rivales_en_orden_de_turno(jugador, juego):
    """Devuelve los NUM_RIVALES jugadores en orden de turno relativo a mí
    (offset +1, +2, +3 ...), independientemente de idJugador absoluto.
    Rellena con None si hay menos rivales que asientos (mesas <4 jugadores).
    """
    n = len(juego.jugadores)
    mi_id = jugador.idJugador
    orden = []
    for offset in range(1, n):
        rival = juego.jugadores[(mi_id + offset) % n]
        orden.append(rival)
    while len(orden) < NUM_RIVALES:
        orden.append(None)
    return orden[:NUM_RIVALES]


def features_estado(pregunta, jugador, juego):
    """Vector de features (dict) de TODO lo que no depende de la candidata:
    mi situación + la de mis rivales. Se combina con `features_candidata`
    para formar la fila completa de una decisión concreta.
    """
    mi_rol = jugador.rol
    hp_ratio = jugador.vidas / jugador.vidasMax if jugador.vidasMax else 1.0
    f = {f"mi_rol_{r}": 1.0 if mi_rol == r else 0.0 for r in ROLES}
    f.update({
        "mis_vidas_ratio": hp_ratio,
        "mi_alcance": jugador.distancia,
        "ronda": juego.ronda,
        "tam_mano": len(pregunta.get("mano", [])),
        "rivales_vivos": sum(1 for j in juego.jugadores if not j.muerto and j.idJugador != jugador.idJugador),
    })
    for k, rival in enumerate(_rivales_en_orden_de_turno(jugador, juego), start=1):
        prefijo = f"rival{k}_"
        if rival is None:
            f[prefijo + "vidas_ratio"] = 0.0
            f[prefijo + "muerto"] = 1.0
            f[prefijo + "es_sheriff"] = 0.0
            f[prefijo + "distancia"] = 0.0
            for eq in EQUIPABLES_RIVAL:
                f[prefijo + eq] = 0.0
            continue
        f[prefijo + "vidas_ratio"] = (rival.vidas / rival.vidasMax) if rival.vidasMax else 0.0
        f[prefijo + "muerto"] = 1.0 if rival.muerto else 0.0
        f[prefijo + "es_sheriff"] = 1.0 if rival.rol == "Sheriff" else 0.0
        f[prefijo + "distancia"] = float(juego.distancia(jugador.idJugador, rival.idJugador))
        equipadas = {c.nombre for c in rival.cartasEquipadas}
        for eq in EQUIPABLES_RIVAL:
            f[prefijo + eq] = 1.0 if eq in equipadas else 0.0
    return f


def features_candidata(nombre_candidata):
    """Vector de features (dict) de la identidad de la carta candidata."""
    f = {f"carta_{n}": 0.0 for n in VOCABULARIO_CARTAS}
    if nombre_candidata in _INDICE_CARTA:
        f[f"carta_{nombre_candidata}"] = 1.0
    f["prioridad_base"] = float(PRIORIDAD_CARTA.get(nombre_candidata, 1))
    return f


def fila_completa(features_estado_dict, nombre_candidata, label):
    """Combina el estado ya calculado con una candidata concreta en una
    única fila (dict) lista para escribir, con su label (0/1)."""
    fila = dict(features_estado_dict)
    fila.update(features_candidata(nombre_candidata))
    fila["label"] = label
    return fila


def nombre_de_opcion(opcion, mano):
    """Traduce una opción cruda ('1', '2', 'FIN', 'PODER') al nombre real
    de la carta que representa, usando la mano de la pregunta."""
    if opcion in ("FIN", "PODER"):
        return opcion
    idx = int(opcion) - 1
    for c in mano:
        if c["indice"] == idx:
            return c["nombre"]
    return None
