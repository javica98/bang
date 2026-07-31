"""
Bot AI para BANG! — sistema de creencias bayesianas + función de evaluación.

Fase 1: creencias estáticas basadas en rol propio + observaciones de acciones.
El bot conoce su rol y deduce quiénes son aliados/enemigos con certeza creciente.
"""

ROLES = ['Sheriff', 'Adjunto', 'Forajido', 'Renegado']

# Qué roles son enemigos según el rol del bot
ENEMIGOS_DE = {
    'Sheriff':  {'Forajido', 'Renegado'},
    'Adjunto':  {'Forajido', 'Renegado'},
    'Forajido': {'Sheriff', 'Adjunto'},
    'Renegado': {'Sheriff', 'Adjunto', 'Forajido'},  # elimina a todos
}

# Señales observables → multiplicador de probabilidad de rol
# (tipo_señal, rol_implicado): factor
SEÑALES = {
    ('ataca_sheriff',   'Forajido'):  4.0,
    ('ataca_sheriff',   'Renegado'):  1.5,
    ('ataca_sheriff',   'Adjunto'):   0.05,
    ('cura_sheriff',    'Adjunto'):   5.0,
    ('cura_sheriff',    'Forajido'):  0.05,
    ('cura_sheriff',    'Renegado'):  0.2,
    ('roba_a_sheriff',  'Forajido'):  2.5,
    ('roba_a_sheriff',  'Renegado'):  1.5,
    ('defiende_sheriff','Adjunto'):   3.0,
    ('defiende_sheriff','Forajido'):  0.1,
    ('ataca_forajido',  'Sheriff'):   3.0,
    ('ataca_forajido',  'Adjunto'):   2.0,
}

# Prioridad de cartas para bot (cuanto mayor, antes se juega)
PRIORIDAD_CARTA = {
    'Cerveza':          50,   # curación urgente (condicional a HP)
    'Whisky':           45,
    'Saloon':           30,
    'Bang':             25,
    'Duelo':            22,
    'Indios':           20,
    'Ametralladora Gatling': 18,
    'Pánico':           15,
    'Ing. Explosiva':   14,
    'Diligencia':       12,
    'Wells Fargo':      11,
    'Barril':           8,
    'Mustang':          7,
    'Cárcel':           6,
    'Dinamita':         5,
    'Mira Telescópica': 4,
    'Volcanic':         3,
    'Schofield':        3,
    'Remington':        3,
    'Rev. Carabina':    3,
    'Winchester':       3,
}


class BotAI:
    """IA para un bot concreto. Mantiene sus propias creencias sobre los rivales."""

    def __init__(self, bot_id):
        self.bot_id = bot_id
        # {jugador_id: {rol: probabilidad}} — se inicializa en primera decisión
        self.creencias = {}
        self._inicializado = False
        # Tracking de intentos fallidos en el turno actual
        self._cartas_fallidas = set()
        self._ultima_eleccion = None   # (indice, len_mano) de la última carta elegida

    # ── Inicialización ──────────────────────────────────────────────────────

    def _inicializar(self, juego):
        """Inicializa creencias la primera vez que se usa, cuando ya hay jugadores."""
        if self._inicializado:
            return
        self._inicializado = True
        for j in juego.jugadores:
            if j.idJugador == self.bot_id:
                continue
            if j.rol == 'Sheriff':
                # Sheriff siempre es conocido
                self.creencias[j.idJugador] = {r: (1.0 if r == 'Sheriff' else 0.0) for r in ROLES}
            else:
                # Distribución uniforme sobre roles no-Sheriff para los demás
                no_sheriff = [r for r in ROLES if r != 'Sheriff']
                self.creencias[j.idJugador] = {r: (1/len(no_sheriff) if r in no_sheriff else 0.0) for r in ROLES}

    # ── Observación ─────────────────────────────────────────────────────────

    def observar(self, señal, actor_id):
        """Actualiza creencias tras observar una acción del jugador actor_id."""
        if actor_id not in self.creencias:
            return
        c = self.creencias[actor_id]
        for rol in ROLES:
            factor = SEÑALES.get((señal, rol), 1.0)
            c[rol] *= factor
        # Renormalizar
        total = sum(c.values())
        if total > 0:
            for r in c:
                c[r] /= total

    # ── Consultas de creencias ───────────────────────────────────────────────

    def prob_enemigo(self, jugador_id, mi_rol):
        """Probabilidad estimada de que jugador_id sea enemigo de este bot."""
        if jugador_id not in self.creencias:
            return 0.0
        enemigos = ENEMIGOS_DE.get(mi_rol, set())
        return sum(self.creencias[jugador_id].get(r, 0) for r in enemigos)

    def sheriff_id(self, juego):
        """Devuelve el ID del Sheriff (siempre visible)."""
        for j in juego.jugadores:
            if j.rol == 'Sheriff':
                return j.idJugador
        return None

    # ── Decisiones ───────────────────────────────────────────────────────────

    def decidir(self, pregunta, jugador, juego):
        """Punto de entrada. Devuelve la respuesta adecuada al tipo de pregunta."""
        if juego is not None:
            self._inicializar(juego)
        tipo = pregunta.get('tipo')

        if tipo == 'elegir_personaje':
            return self._elegir_personaje(pregunta)
        if tipo == 'elegir_carta':
            return self._elegir_carta(pregunta, jugador, juego)
        if tipo == 'elegir_jugador':
            return self._elegir_jugador(pregunta, jugador, juego)
        if tipo == 'elegir_carta_rival':
            return self._elegir_carta_rival(pregunta)
        if tipo == 'elegir_lucky_duke':
            return self._elegir_lucky_duke(pregunta)
        if tipo == 'elegir_robo_jesse':
            return self._elegir_robo_jesse(pregunta, juego)
        if tipo == 'elegir_robo_pedro':
            return self._elegir_robo_pedro(pregunta)
        if tipo == 'elegir_kit_carlson':
            return self._elegir_kit_carlson(pregunta)
        if tipo == 'elegir_almacen_carta':
            return self._elegir_almacen(pregunta, jugador, juego)
        if tipo == 'prompt':
            return self._responder_prompt(pregunta, jugador, juego)
        return 'None'

    def _elegir_personaje(self, pregunta):
        # Elige el personaje con más vidas (más resistente)
        pa = pregunta['personaje_a']
        pb = pregunta['personaje_b']
        return 'A' if pa['vidas'] >= pb['vidas'] else 'B'

    def _elegir_carta(self, pregunta, jugador, juego):
        mano = pregunta.get('mano', [])
        opciones = set(str(o) for o in pregunta.get('opciones', []))
        mi_rol = jugador.rol if jugador else None
        hp_ratio = (jugador.vidas / jugador.vidasMax) if (jugador and jugador.vidasMax) else 1

        # Si la última elección fue rechazada (mano no cambió), marcarla fallida
        if self._ultima_eleccion is not None:
            prev_idx, prev_len = self._ultima_eleccion
            if prev_len == len(mano):
                self._cartas_fallidas.add(prev_idx)
            else:
                self._cartas_fallidas.clear()
            self._ultima_eleccion = None

        jugables = [c for c in mano
                    if str(c['indice'] + 1) in opciones
                    and c['indice'] not in self._cartas_fallidas]

        def elegir(c):
            """Registra la elección y devuelve el valor."""
            self._ultima_eleccion = (c['indice'], len(mano))
            return str(c['indice'] + 1)

        # ── 1. Curación urgente (HP ≤ 50%) ──────────────────────────────
        if hp_ratio <= 0.5:
            for c in jugables:
                if c['nombre'] in ('Cerveza', 'Whisky'):
                    return elegir(c)

        # ── 2. Saloon si hay 2+ jugadores con HP bajo ────────────────────
        jugadores_vivos = [j for j in juego.jugadores if not j.muerto] if juego else []
        if len([j for j in jugadores_vivos if j.vidas <= 2]) >= 2:
            for c in jugables:
                if c['nombre'] == 'Saloon':
                    return elegir(c)

        # ── 3. Ataque si hay enemigos al alcance ─────────────────────────
        enemigos = self._enemigos_al_alcance(jugador, juego)
        if enemigos:
            for c in jugables:
                if c['nombre'] in ('Bang', 'Duelo', 'Indios', 'Ametralladora Gatling'):
                    return elegir(c)

        # ── 4. Pánico / Ing. Explosiva ───────────────────────────────────
        for c in jugables:
            if c['nombre'] in ('Pánico', 'Panico', 'Ing. Explosiva'):
                return elegir(c)

        # ── 5. Robo extra ────────────────────────────────────────────────
        for c in jugables:
            if c['nombre'] in ('Diligencia', 'Wells Fargo'):
                return elegir(c)

        # ── 6. Objetos defensivos ────────────────────────────────────────
        ya_equipados = {eq.nombre for eq in getattr(jugador, 'cartasEquipadas', [])}
        for c in jugables:
            if c['nombre'] in ('Barril', 'Mustang', 'Mira Telescópica') and c['nombre'] not in ya_equipados:
                return elegir(c)

        # ── 7. Mejora de arma ────────────────────────────────────────────
        for c in jugables:
            if c['nombre'] in ('Volcanic', 'Winchester', 'Rev. Carabina', 'Remington', 'Schofield'):
                return elegir(c)

        # ── 8. Curación no urgente ───────────────────────────────────────
        if hp_ratio < 1.0:
            for c in jugables:
                if c['nombre'] in ('Cerveza', 'Whisky'):
                    return elegir(c)

        # ── 9. Cárcel ────────────────────────────────────────────────────
        for c in jugables:
            if c['nombre'] == 'Cárcel':
                return elegir(c)

        # ── 10. Descarte forzado: elegir la carta menos valiosa ───────────
        if not pregunta.get('permitir_fin', True) and jugables:
            peor = min(jugables, key=lambda c: PRIORIDAD_CARTA.get(c['nombre'], 1))
            return elegir(peor)

        return 'FIN'

    def _elegir_jugador(self, pregunta, jugador, juego):
        validos = pregunta.get('jugadores_validos', [])
        if not validos:
            return 'None'
        mi_rol = jugador.rol

        def score(jid):
            j = next((x for x in juego.jugadores if x.idJugador == jid), None)
            if not j:
                return -999
            p_enemigo = self.prob_enemigo(jid, mi_rol)
            # Bonus por pocas vidas (más fácil de eliminar)
            peligro = (j.vidasMax - j.vidas) * 0.5
            # Penalización si el Sheriff es aliado
            if mi_rol == 'Adjunto' and j.rol == 'Sheriff':
                return -10
            return p_enemigo * 10 + peligro

        mejor = max(validos, key=score)
        return str(mejor)

    def _elegir_carta_rival(self, pregunta):
        # Preferir robar de mano; si no tiene, tomar equipada
        if pregunta.get('mano_size', 0) > 0:
            return 'mano:0'
        equipadas = pregunta.get('equipadas', [])
        if equipadas:
            return f"equipo:{equipadas[0]['indice']}"
        return 'mano:0'

    def _elegir_lucky_duke(self, pregunta):
        # Elegir la carta con palo de corazones/diamantes (más probable salvar)
        for key in ('carta1', 'carta2'):
            c = pregunta.get(key, {})
            if c.get('palo') in ('♥', '♦', 'corazones', 'diamantes'):
                return '0' if key == 'carta1' else '1'
        return '0'

    def _elegir_robo_jesse(self, pregunta, juego):
        rivales = pregunta.get('rivales', [])
        if not rivales:
            return 'None'
        # Robar del rival con más cartas
        def num_cartas(jid):
            j = next((x for x in juego.jugadores if x.idJugador == jid), None)
            return len(j.cartasMano) if j else 0
        return str(max(rivales, key=num_cartas))

    def _elegir_robo_pedro(self, pregunta):
        # Coger del descarte si es Bang!, Cerveza o carta de ataque
        c = pregunta.get('carta_top', {})
        utiles = ('Bang', 'Cerveza', 'Whisky', 'Duelo', 'Indios', 'Fallaste',
                  'Ametralladora Gatling', 'Barril', 'Mustang')
        return 'SI' if c.get('nombre') in utiles else 'NO'

    def _elegir_kit_carlson(self, pregunta):
        cartas = pregunta.get('cartas', [])
        if not cartas:
            return '0'
        # Devolver la carta menos útil (ultima de la lista por defecto)
        inútiles = ('Fallaste', 'Cárcel', 'Dinamita')
        for i, c in enumerate(cartas):
            if c['nombre'] in inútiles:
                return str(i)
        return str(len(cartas) - 1)

    def _elegir_almacen(self, pregunta, jugador, juego):
        cartas = pregunta.get('cartas', [])
        if not cartas:
            return '0'
        hp_ratio = jugador.vidas / jugador.vidasMax if jugador.vidasMax else 1

        def score(c):
            n = c['nombre']
            base = PRIORIDAD_CARTA.get(n, 1)
            # Bonus curación si HP bajo
            if n in ('Cerveza', 'Whisky') and hp_ratio < 0.75:
                base += 30
            # Bonus ataque si hay enemigos
            if n in ('Bang', 'Duelo') and self._enemigos_al_alcance(jugador, juego):
                base += 10
            return base

        mejor_idx = max(range(len(cartas)), key=lambda i: score(cartas[i]))
        return str(mejor_idx)

    def _responder_prompt(self, pregunta, jugador, juego):
        texto = pregunta.get('texto', '').lower()
        opciones = pregunta.get('opciones', [])
        # Responder a ataques (Bang/Fallaste)
        if 'te han atacado' in texto or 'fallaste' in texto or 'bang' in texto:
            if 'SI' in opciones:
                # Intentar esquivar: buscar carta en mano
                mano = getattr(jugador, 'cartasMano', [])
                for c in mano:
                    if c.nombre in ('Fallaste', 'Bang'):
                        return 'SI'
            return 'NO'
        # Descartar: elegir la carta menos valiosa
        if opciones and all(o.isdigit() for o in opciones):
            mano = list(getattr(jugador, 'cartasMano', []))
            if mano:
                def valor(i):
                    n = mano[i].nombre if i < len(mano) else ''
                    return PRIORIDAD_CARTA.get(n, 1)
                peor = min((int(o) - 1 for o in opciones if o.isdigit()), key=valor, default=0)
                return str(peor + 1)
        return opciones[0] if opciones else 'None'

    # ── Utilidades ──────────────────────────────────────────────────────────

    def _enemigos_al_alcance(self, jugador, juego):
        mi_rol = jugador.rol
        resultado = []
        for j in juego.jugadores:
            if j.muerto or j.idJugador == jugador.idJugador:
                continue
            p_enemigo = self.prob_enemigo(j.idJugador, mi_rol)
            dist = juego.distancia(jugador.idJugador, j.idJugador)
            alcance = jugador.distancia  # distancia de disparo del arma
            if p_enemigo > 0.4 and dist <= alcance:
                resultado.append(j)
        return resultado
