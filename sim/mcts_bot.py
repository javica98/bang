"""Bot MCTS (Monte Carlo Tree Search / UCT) — Fase 2 del roadmap de IA.

Para cada decisión de "qué carta jugar", clona el estado de la partida,
sortea un mundo (roles ocultos de los rivales) según las creencias
bayesianas del propio bot, y evalúa cada carta jugable mediante rollouts
completos que usan las heurísticas de Fase 1 (BotAI) tanto para el resto
de este turno como para el resto de la partida. Selecciona la acción con
un árbol UCT de un nivel (UCB1 sobre las cartas jugables).

Todo lo que NO es "qué carta jugar" (a quién apuntar, si esquivar, etc.)
se delega directamente al BotAI heurístico interno — el MCTS no lo decide,
tal y como se acordó para esta primera versión.

Simplificación deliberada: el mundo muestreado solo oculta ROLES. Las
cartas reales en la mano de los rivales se ven tal cual en la simulación
(estado clonado real), no se "inventan" manos plausibles. Es la variante
más simple de MCTS con información oculta (a veces llamada determinista/
"cheating" MCTS) — más simple que un ISMCTS completo pero ya útil.

Limitación conocida: en pruebas con presupuesto de ~100ms, alrededor de un
20% de las partidas se alargan mucho más de lo normal (varios cientos de
pasos, a veces por encima de max_pasos) antes de resolverse. No se ha
aislado la causa exacta — no es el bucle de "elegir una acción inválida
repetidamente" (ya corregido), las partidas SÍ progresan turno a turno.
Es probablemente un efecto de que, con pocos rollouts, las estimaciones de
UCB1 son ruidosas y a veces el bot cae en juego pasivo prolongado. Mientras
no se investigue más a fondo, usa un `max_pasos` generoso (varios miles) al
ejecutar partidas con este bot para no cortar partidas legítimamente largas.
"""
import builtins
import contextlib
import math
import os
import random
import sys
import time
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bang_game import Juego  # noqa: E402
from ClasesAux import Jugador  # noqa: E402
from bot_ai import BotAI  # noqa: E402
from sim_io import SimIO, PasosExcedidos  # noqa: E402

PRESUPUESTO_DEFECTO_S = 0.2
C_EXPLORACION_DEFECTO = 1.4
MAX_PASOS_ROLLOUT_DEFECTO = 1500


@contextlib.contextmanager
def _silenciar_print():
    """Los rollouts corren partidas completas por dentro; sin esto, cada una
    imprimiría su narrativa entera mezclada con la de la partida real."""
    orig = builtins.print
    builtins.print = lambda *a, **k: None
    try:
        yield
    finally:
        builtins.print = orig


def _clonar_jugador_rapido(j):
    nuevo = Jugador.__new__(Jugador)
    nuevo.__dict__.update(j.__dict__)
    nuevo.cartasMano = list(j.cartasMano)
    nuevo.cartasEquipadas = list(j.cartasEquipadas)
    return nuevo


def _clonar_juego(juego):
    """Clon rápido del estado de la partida para un rollout (sin el io
    real: bots/colas). Evita copy.deepcopy —recorre reflexivamente todo
    el grafo de objetos y era, con diferencia, el coste dominante de cada
    rollout— aprovechando que Carta y Personaje no se mutan nunca después
    de construirse (numero/palo se asignan una vez en info_extract y no
    vuelven a tocarse): basta con compartir esas referencias y clonar
    solo lo que sí cambia turno a turno (las listas que las contienen y
    los Jugador: vidas, mano, equipo, contBang...).
    """
    clon = Juego.__new__(Juego)
    clon.__dict__.update(juego.__dict__)
    clon.jugadores = [_clonar_jugador_rapido(j) for j in juego.jugadores]
    clon.baraja = list(juego.baraja)
    clon.monton_descartes = list(juego.monton_descartes)
    clon.jugadores_eliminados = list(juego.jugadores_eliminados)
    clon.io = None
    return clon


def _muestrear_mundo(juego_clon, mi_id, creencias):
    """Reasigna roles a los rivales de identidad desconocida, respetando el
    multiset real de roles de la partida y ponderando por las creencias
    bayesianas del bot. Quedan fijos con su rol real: el propio bot, el
    Sheriff (siempre público) y cualquier jugador ya muerto (su rol queda
    revelado al morir).
    """
    jugadores = juego_clon.jugadores
    fijos = set()
    for j in jugadores:
        if j.idJugador == mi_id or j.rol == "Sheriff" or j.muerto:
            fijos.add(j.idJugador)

    total = Counter(j.rol for j in jugadores)
    for jid in fijos:
        total[jugadores[jid].rol] -= 1
    pool = []
    for rol, n in total.items():
        pool.extend([rol] * max(n, 0))

    desconocidos = [j.idJugador for j in jugadores if j.idJugador not in fijos]
    random.shuffle(desconocidos)
    for jid in desconocidos:
        if not pool:
            break
        creencia = creencias.get(jid, {})
        pesos = [max(creencia.get(r, 0.0), 1e-6) for r in pool]
        total_peso = sum(pesos)
        if total_peso <= 0:
            idx = random.randrange(len(pool))
        else:
            r = random.uniform(0, total_peso)
            acumulado = 0.0
            idx = len(pool) - 1
            for i, p in enumerate(pesos):
                acumulado += p
                if r <= acumulado:
                    idx = i
                    break
        jugadores[jid].rol = pool.pop(idx)


def _mezclar_manos_desconocidas(juego_clon, mi_id):
    """Además del rol, la incertidumbre real incluye qué cartas concretas
    tiene cada rival en la mano — solo se conoce el NÚMERO de cartas, no
    cuáles. Junta las manos ajenas (menos la propia) con el mazo en un
    pool y las reparte de nuevo al azar respetando el tamaño de cada mano
    y del mazo, para que el rollout no "haga trampa" viendo las cartas
    reales de los rivales. Las cartas equipadas y el descarte SON
    públicos (se ven en la mesa), no se tocan.
    """
    jugadores = juego_clon.jugadores
    pool = list(juego_clon.baraja)
    tamaños = {}
    for j in jugadores:
        if j.idJugador == mi_id or j.muerto:
            continue
        tamaños[j.idJugador] = len(j.cartasMano)
        pool.extend(j.cartasMano)
    random.shuffle(pool)
    for jid, n in tamaños.items():
        jugadores[jid].cartasMano = pool[:n]
        pool = pool[n:]
    juego_clon.baraja = pool


class _RolloutIO(SimIO):
    """SimIO que fuerza UNA sola decisión (la que se está evaluando) y
    delega el resto de la partida —incluido lo que queda del turno
    actual— al BotAI heurístico de cada jugador, propio bot MCTS incluido.
    """

    def __init__(self, bots, jugador_forzado_id, accion_forzada, max_pasos=None):
        super().__init__(bots, max_pasos=max_pasos)
        self._jugador_forzado_id = jugador_forzado_id
        self._accion_forzada = accion_forzada
        self._forzado_usado = False

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        if not self._forzado_usado and jugador.idJugador == self._jugador_forzado_id:
            self._forzado_usado = True
            self.current_jugador = jugador
            self._asking_id = jugador.idJugador
            self.pasos += 1
            return self._accion_forzada
        return super().elegir_carta(jugador, text, opciones, permitir_fin, permitir_poder)


class _NodoAccion:
    __slots__ = ("visitas", "valor")

    def __init__(self):
        self.visitas = 0
        self.valor = 0.0


class MCTSBotAI:
    """IA basada en MCTS/UCT para la decisión de qué carta jugar.

    Envuelve un BotAI heurístico normal: lo usa para todas las preguntas
    que no son "elegir_carta", y para mantener las creencias bayesianas
    (recibe observar() igual que un BotAI corriente).
    """

    def __init__(self, bot_id, presupuesto_s=PRESUPUESTO_DEFECTO_S,
                 c_exploracion=C_EXPLORACION_DEFECTO,
                 max_pasos_rollout=MAX_PASOS_ROLLOUT_DEFECTO):
        self.bot_id = bot_id
        self.presupuesto_s = presupuesto_s
        self.c = c_exploracion
        self.max_pasos_rollout = max_pasos_rollout
        self._heuristico = BotAI(bot_id)
        self.ultima_busqueda = None  # stats de la última decisión, para depurar/medir
        # Igual que BotAI: si la última acción elegida no cambió la mano (p.ej.
        # jugar Fallaste fuera de una respuesta a Bang, que es un no-op), se
        # descarta esa opción la próxima vez para no quedarse en bucle.
        self._ultima_eleccion = None
        self._acciones_fallidas = set()

    def observar(self, señal, actor_id):
        self._heuristico.observar(señal, actor_id)

    def decidir(self, pregunta, jugador, juego):
        if juego is not None:
            self._heuristico._inicializar(juego)
        if pregunta.get('tipo') == 'elegir_carta':
            return self._decidir_carta_mcts(pregunta, jugador, juego)
        return self._heuristico.decidir(pregunta, jugador, juego)

    def _decidir_carta_mcts(self, pregunta, jugador, juego):
        mano = pregunta.get('mano', [])
        # ojo: pregunta['opciones'] solo trae los índices de carta; FIN/PODER
        # llegan como flags aparte (permitir_fin/permitir_poder) — hay que
        # añadirlos a mano como candidatos, si no el bot nunca puede acabar
        # el turno (así lo hace ConsoleIO, y es lo que asume el resto del motor).
        opciones_todas = list(pregunta.get('opciones', []))
        if pregunta.get('permitir_fin', True):
            opciones_todas.append('FIN')
        if pregunta.get('permitir_poder', False):
            opciones_todas.append('PODER')

        if self._ultima_eleccion is not None:
            prev_accion, prev_len = self._ultima_eleccion
            if prev_len == len(mano):
                self._acciones_fallidas.add(prev_accion)
            else:
                self._acciones_fallidas.clear()
            self._ultima_eleccion = None
        else:
            self._acciones_fallidas.clear()

        opciones = [op for op in opciones_todas if op not in self._acciones_fallidas]
        if not opciones:
            opciones = opciones_todas

        if len(opciones) <= 1:
            elegido = opciones[0] if opciones else 'FIN'
            self._ultima_eleccion = (elegido, len(mano))
            return elegido

        nodos = {op: _NodoAccion() for op in opciones}

        def rollout(accion):
            return self._rollout(accion, jugador, juego)

        # Primera pasada: cada acción se prueba al menos una vez, sin
        # depender del presupuesto de tiempo (evita decidir a ciegas si el
        # presupuesto es demasiado ajustado para ni siquiera una ronda).
        pendientes = list(opciones)
        random.shuffle(pendientes)
        for accion in pendientes:
            n = nodos[accion]
            n.visitas += 1
            n.valor += rollout(accion)

        def ucb1(accion):
            n = nodos[accion]
            total_visitas = sum(x.visitas for x in nodos.values())
            explotacion = n.valor / n.visitas
            exploracion = self.c * math.sqrt(math.log(total_visitas) / n.visitas)
            return explotacion + exploracion

        t0 = time.perf_counter()
        iteraciones = len(opciones)
        while time.perf_counter() - t0 < self.presupuesto_s:
            accion = max(opciones, key=ucb1)
            n = nodos[accion]
            n.visitas += 1
            n.valor += rollout(accion)
            iteraciones += 1

        self.ultima_busqueda = {
            op: (n.visitas, n.valor / n.visitas if n.visitas else 0.0)
            for op, n in nodos.items()
        }
        # "Robust child": la más visitada, no la de mejor media (más estable
        # cuando el presupuesto es pequeño y hay ruido en los rollouts).
        mejor = max(opciones, key=lambda op: nodos[op].visitas)
        self._ultima_eleccion = (mejor, len(mano))
        return mejor

    def _rollout(self, accion, jugador, juego):
        clon = _clonar_juego(juego)
        _muestrear_mundo(clon, self.bot_id, self._heuristico.creencias)
        _mezclar_manos_desconocidas(clon, self.bot_id)
        bots = {j.idJugador: BotAI(j.idJugador) for j in clon.jugadores}
        io = _RolloutIO(bots, jugador_forzado_id=jugador.idJugador,
                         accion_forzada=accion, max_pasos=self.max_pasos_rollout)
        clon.io = io
        io.set_game(clon)
        try:
            with _silenciar_print():
                clon._resto_turno(jugador.idJugador)
                if not clon.game_over:
                    clon.partida(continuar=True)
        except PasosExcedidos:
            return 0.0
        return 1.0 if self._gano_mi_bando(clon.ganador, jugador.rol) else 0.0

    @staticmethod
    def _gano_mi_bando(ganador, mi_rol_real):
        if mi_rol_real in ('Sheriff', 'Ayudante'):
            return ganador == 'Sheriff'
        if mi_rol_real == 'Forajido':
            return ganador == 'Forajidos'
        if mi_rol_real == 'Renegado':
            return ganador == 'Renegado'
        return False
