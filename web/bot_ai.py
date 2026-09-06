"""
Bot AI para BANG! — sistema de creencias bayesianas + función de evaluación.

Fase 1: creencias estáticas basadas en rol propio + observaciones de acciones.
El bot conoce su rol y deduce quiénes son aliados/enemigos con certeza creciente.
"""

ROLES = ['Sheriff', 'Ayudante', 'Forajido', 'Renegado']

# Probabilidad mínima de creencias para tratar a alguien como enemigo.
# Barrido con el simulador (800 partidas/combo): 0.3 dio consistentemente
# mejor tasa de victoria para el Sheriff (7.6% vs 4.6% con el antiguo 0.4)
# sin perjudicar a Forajidos/Renegado — umbral más bajo = los bots
# reaccionan antes ante sospechas todavía débiles, en vez de esperar a
# tener casi certeza.
UMBRAL_ENEMIGO = 0.3

# Ratio de vidas al que el Sheriff empieza a curarse con urgencia (el resto
# de roles usan 0.5, ver _elegir_carta) — separado en constante para poder
# barrerlo con el simulador en vez de dejarlo fijo a ojo.
UMBRAL_CURACION_SHERIFF = 0.65

# Qué roles son enemigos según el rol del bot
ENEMIGOS_DE = {
    'Sheriff':  {'Forajido', 'Renegado'},
    'Ayudante':  {'Forajido', 'Renegado'},
    'Forajido': {'Sheriff', 'Ayudante'},
    'Renegado': {'Sheriff', 'Ayudante', 'Forajido'},  # elimina a todos
}

# Señales observables → multiplicador de probabilidad de rol
# (tipo_señal, rol_implicado): factor
SEÑALES = {
    ('ataca_sheriff',   'Forajido'):  4.0,
    ('ataca_sheriff',   'Renegado'):  1.5,
    ('ataca_sheriff',   'Ayudante'):   0.05,
    ('cura_sheriff',    'Ayudante'):   5.0,
    ('cura_sheriff',    'Forajido'):  0.05,
    ('cura_sheriff',    'Renegado'):  0.2,
    ('roba_a_sheriff',  'Forajido'):  2.5,
    ('roba_a_sheriff',  'Renegado'):  1.5,
    ('defiende_sheriff','Ayudante'):   3.0,
    ('defiende_sheriff','Forajido'):  0.1,
    ('ataca_forajido',  'Sheriff'):   3.0,
    ('ataca_forajido',  'Ayudante'):   2.0,
}

# Prioridad de cartas para bot (cuanto mayor, antes se juega)
PRIORIDAD_CARTA = {
    'Cerveza':          50,   # curación urgente (condicional a HP)
    'Whisky':           45,
    'Saloon':           30,
    'Bang':             25,
    'Duelo':            22,
    'Fallaste':         20,   # defensa: nunca debe ser de las primeras en descartarse
    'Indios':           20,
    'Ametralladora Gatling': 18,
    'Panico':           15,
    'Ingenua Explosiva': 14,
    'Diligencia':       12,
    'Wells Fargo':      11,
    'Barril':           8,
    'Mustang':          7,
    'Carcel':           6,
    'Dinamita':         5,
    'Mira Telescopica': 4,
    'Volcanic':         3,
    'Schofield':        3,
    'Remington':        3,
    'Caravina Revolver': 3,
    'Winchester':       3,
}
# Nota: los nombres de arriba deben coincidir EXACTAMENTE con la columna
# `nombre` de cartas.csv (sin tildes, sin abreviar) — así es como llegan
# los objetos Carta en tiempo de ejecución. Antes de 2026-08-30 varias de
# estas claves usaban grafías con tilde/abreviadas que nunca hacían match
# (p.ej. 'Cárcel', 'Rev. Carabina', 'Ing. Explosiva'), dejando esas cartas
# con prioridad mínima y sin disparar nunca sus reglas dedicadas.


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
        # {jugador_id: nº de veces que ha atacado al Sheriff} — evidencia directa,
        # más fiable que la inferencia bayesiana para coordinar represalias.
        self.amenaza_sheriff = {}

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
        if señal == 'ataca_sheriff':
            self.amenaza_sheriff[actor_id] = self.amenaza_sheriff.get(actor_id, 0) + 1
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
            return self._elegir_robo_pedro(pregunta, jugador, juego)
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
        else:
            # Nuevo ciclo de decisión (turno nuevo o FIN aceptado): limpiar fallos obsoletos
            self._cartas_fallidas.clear()

        jugables = [c for c in mano
                    if str(c['indice'] + 1) in opciones
                    and c['indice'] not in self._cartas_fallidas]

        def elegir(c):
            """Registra la elección y devuelve el valor."""
            self._ultima_eleccion = (c['indice'], len(mano))
            return str(c['indice'] + 1)

        # ── 1. Curación urgente ────────────────────────────────────────
        # El Sheriff se cura antes: perderlo termina la partida al instante,
        # así que su vida vale más que la de cualquier otro rol.
        # Si llevo Dinamita equipada, también antes: puede explotarme 3 vidas
        # de golpe en mi próxima fase de robo.
        umbral_curacion = UMBRAL_CURACION_SHERIFF if mi_rol == 'Sheriff' else 0.5
        tiene_dinamita_propia = any(
            eq.nombre == 'Dinamita' for eq in getattr(jugador, 'cartasEquipadas', [])
        )
        if tiene_dinamita_propia:
            umbral_curacion = max(umbral_curacion, 0.75)
        if hp_ratio <= umbral_curacion:
            for c in jugables:
                if c['nombre'] in ('Cerveza', 'Whisky'):
                    return elegir(c)

        # ── 2. Saloon si hay 2+ jugadores con HP bajo que no son enemigos ─
        # Curar a un enemigo herido con Saloon juega en mi contra, así que
        # solo cuentan los heridos que soy yo o que no tengo por enemigos.
        jugadores_vivos = [j for j in juego.jugadores if not j.muerto] if juego else []
        heridos = [j for j in jugadores_vivos if j.vidas <= 2]
        heridos_valiosos = [
            j for j in heridos
            if j.idJugador == jugador.idJugador or self.prob_enemigo(j.idJugador, mi_rol) <= UMBRAL_ENEMIGO
        ]
        if len(heridos_valiosos) >= 2:
            for c in jugables:
                if c['nombre'] == 'Saloon':
                    return elegir(c)

        # ── 3. Ataque si hay enemigos al alcance ─────────────────────────
        # El Renegado gana siendo el último en pie: si va de forajido agresivo
        # desde el turno 1 muere en el fuego cruzado antes de tener oportunidad.
        # Se mantiene pasivo mientras la partida tenga >3 jugadores vivos; el
        # umbral de "a quién le vale la pena rematar" sube gradualmente según
        # van muriendo jugadores, en vez de pasar de golpe de "solo rematar a
        # 1 vida" a "sin restricción" (útil sobre todo en mesas de 5-7, donde
        # hay más margen entre "recién empezada" y "quedan 3").
        cauteloso = mi_rol == 'Renegado' and len(jugadores_vivos) > 3
        enemigos = self._enemigos_al_alcance(jugador, juego)
        if cauteloso:
            total_jugadores = len(juego.jugadores) if juego else len(jugadores_vivos)
            fraccion_muertos = 1 - (len(jugadores_vivos) / total_jugadores if total_jugadores else 1)
            umbral_vidas_objetivo = 1 + round(fraccion_muertos * 4)
            enemigos = [e for e in enemigos if e.vidas <= umbral_vidas_objetivo]
        if enemigos:
            for c in jugables:
                if c['nombre'] in ('Bang', 'Duelo', 'Indios', 'Ametralladora Gatling'):
                    return elegir(c)

        # ── 3b. Cárcel a un rival peligroso que no alcanzo con el arma ───
        if not cauteloso:
            objetivo_carcel = self._mejor_objetivo_carcel(jugador, juego)
            if objetivo_carcel is not None:
                for c in jugables:
                    if c['nombre'] == 'Carcel':
                        return elegir(c)

        # ── 4. Pánico / Ingenua Explosiva ─────────────────────────────────
        for c in jugables:
            if c['nombre'] in ('Panico', 'Ingenua Explosiva'):
                return elegir(c)

        # ── 5. Robo extra ────────────────────────────────────────────────
        for c in jugables:
            if c['nombre'] in ('Diligencia', 'Wells Fargo'):
                return elegir(c)

        # ── 6. Objetos defensivos ────────────────────────────────────────
        ya_equipados = {eq.nombre for eq in getattr(jugador, 'cartasEquipadas', [])}
        for c in jugables:
            if c['nombre'] in ('Barril', 'Mustang') and c['nombre'] not in ya_equipados:
                return elegir(c)

        # ── 6b. Mira Telescópica: es ofensiva (–1 distancia), no defensiva.
        # Solo merece la pena si de verdad mete a algún enemigo dentro de mi
        # alcance que ahora mismo se me queda a 1 casilla de distancia.
        if 'Mira Telescopica' not in ya_equipados and self._mira_telescopica_util(jugador, juego):
            for c in jugables:
                if c['nombre'] == 'Mira Telescopica':
                    return elegir(c)

        # ── 7. Mejora de arma ────────────────────────────────────────────
        for c in jugables:
            if c['nombre'] in ('Volcanic', 'Winchester', 'Caravina Revolver', 'Remington', 'Schofield'):
                return elegir(c)

        # ── 8. Curación no urgente ───────────────────────────────────────
        if hp_ratio < 1.0:
            for c in jugables:
                if c['nombre'] in ('Cerveza', 'Whisky'):
                    return elegir(c)

        # ── 9. Cárcel ────────────────────────────────────────────────────
        for c in jugables:
            if c['nombre'] == 'Carcel':
                return elegir(c)

        # ── 10. Descarte forzado: elegir la carta menos valiosa ───────────
        if not pregunta.get('permitir_fin', True):
            candidatas = jugables or [c for c in mano if str(c['indice'] + 1) in opciones]
            if candidatas:
                peor = min(candidatas, key=lambda c: PRIORIDAD_CARTA.get(c['nombre'], 1))
                return elegir(peor)

        return 'FIN'

    def _elegir_jugador(self, pregunta, jugador, juego):
        validos = pregunta.get('jugadores_validos', [])
        if not validos:
            return 'None'
        mi_rol = jugador.rol

        # El Renegado gana siendo el último en pie: le conviene que Sheriff y
        # Forajidos se desgasten mutuamente el mayor tiempo posible. Cuando
        # ataca, se inclina contra el bando que ahora mismo pesa más (en
        # vidas), no contra "todos por igual" como haría un rol normal.
        bando_fuerte = None
        if mi_rol == 'Renegado':
            fuerza_sheriff, fuerza_forajido = self._fuerza_bandos(jugador, juego)
            bando_fuerte = 'Sheriff' if fuerza_sheriff >= fuerza_forajido else 'Forajido'

        def score(jid):
            j = next((x for x in juego.jugadores if x.idJugador == jid), None)
            if not j:
                return -999
            p_enemigo = self.prob_enemigo(jid, mi_rol)
            # Bonus por pocas vidas (más fácil de eliminar)
            peligro = (j.vidasMax - j.vidas) * 0.5
            # Penalización si el Sheriff es aliado
            if mi_rol == 'Ayudante' and j.rol == 'Sheriff':
                return -10
            # Coordinación: Sheriff y Ayudantes se vengan de quien ya ha disparado al Sheriff
            represalia = 0
            if mi_rol in ('Sheriff', 'Ayudante'):
                represalia = self.amenaza_sheriff.get(jid, 0) * 8
            bando_bonus = 0
            if bando_fuerte is not None:
                c = self.creencias.get(jid, {})
                if bando_fuerte == 'Sheriff':
                    bando_bonus = (c.get('Sheriff', 0) + c.get('Ayudante', 0)) * 10
                else:
                    bando_bonus = c.get('Forajido', 0) * 10
            return p_enemigo * 10 + peligro + represalia + bando_bonus

        mejor = max(validos, key=score)
        return str(mejor)

    def _elegir_carta_rival(self, pregunta):
        # Preferir robar de mano; si no tiene, tomar la carta equipada más valiosa
        # (su arma o su Barril), no la primera que aparezca.
        if pregunta.get('mano_size', 0) > 0:
            return 'mano:0'
        equipadas = pregunta.get('equipadas', [])
        if equipadas:
            mejor = max(equipadas, key=lambda c: PRIORIDAD_CARTA.get(c['nombre'], 1))
            return f"equipo:{mejor['indice']}"
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

    def _elegir_robo_pedro(self, pregunta, jugador, juego):
        # Coger del descarte solo si vale más que una carta media al azar del
        # mazo (mismo criterio de valor que usa el Almacén).
        c = pregunta.get('carta_top', {})
        return 'SI' if self._valor_carta(c.get('nombre', ''), jugador, juego) >= 7 else 'NO'

    def _elegir_kit_carlson(self, pregunta):
        cartas = pregunta.get('cartas', [])
        if not cartas:
            return '0'
        # Devolver la carta menos útil (ultima de la lista por defecto)
        # Fallaste NO entra aquí: es defensa, no conviene devolverla al mazo.
        inútiles = ('Carcel', 'Dinamita')
        for i, c in enumerate(cartas):
            if c['nombre'] in inútiles:
                return str(i)
        return str(len(cartas) - 1)

    def _elegir_almacen(self, pregunta, jugador, juego):
        cartas = pregunta.get('cartas', [])
        if not cartas:
            return '0'
        # El Almacén se reparte por turnos: lo que no me llevo yo, se lo
        # puede llevar el rival más peligroso. Si una carta le vale mucho
        # más a él que a mí, vale la pena "gastarla" en negársela aunque no
        # sea mi mejor opción — no solo maximizar mi propio valor.
        PESO_NEGACION = 0.3
        rival = None
        mejor_prob = UMBRAL_ENEMIGO
        for j in juego.jugadores:
            if j.muerto or j.idJugador == jugador.idJugador:
                continue
            p = self.prob_enemigo(j.idJugador, jugador.rol)
            if p > mejor_prob:
                mejor_prob = p
                rival = j

        def score(c):
            nombre = c['nombre']
            valor_propio = self._valor_carta(nombre, jugador, juego)
            if rival is None:
                return valor_propio
            valor_rival = self._valor_carta(nombre, rival, juego)
            return valor_propio - PESO_NEGACION * max(0, valor_rival - valor_propio)

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

    def _fuerza_bandos(self, jugador, juego):
        """Suma de vidas del bando Sheriff (Sheriff+Ayudante) y del bando
        Forajido, ponderada por mis creencias sobre quién es cada uno.
        Usado por el Renegado para saber a qué bando le conviene oponerse.
        """
        fuerza_sheriff = 0.0
        fuerza_forajido = 0.0
        for j in juego.jugadores:
            if j.muerto or j.idJugador == jugador.idJugador:
                continue
            c = self.creencias.get(j.idJugador)
            if not c:
                continue
            fuerza_sheriff += (c.get('Sheriff', 0) + c.get('Ayudante', 0)) * j.vidas
            fuerza_forajido += c.get('Forajido', 0) * j.vidas
        return fuerza_sheriff, fuerza_forajido

    def _valor_carta(self, nombre, jugador, juego):
        """Valor situacional de una carta conocida (por nombre): prioridad base
        más bonus si cura y estoy herido, o si ataca y tengo enemigos al alcance.
        Usado para decidir qué coger (Almacén, Pedro Ramírez) o qué descartar.
        """
        base = PRIORIDAD_CARTA.get(nombre, 1)
        hp_ratio = jugador.vidas / jugador.vidasMax if (jugador and jugador.vidasMax) else 1
        if nombre in ('Cerveza', 'Whisky') and hp_ratio < 0.75:
            base += 30
        if nombre in ('Bang', 'Duelo') and self._enemigos_al_alcance(jugador, juego):
            base += 10
        return base

    def _enemigos_al_alcance(self, jugador, juego):
        mi_rol = jugador.rol
        resultado = []
        for j in juego.jugadores:
            if j.muerto or j.idJugador == jugador.idJugador:
                continue
            p_enemigo = self.prob_enemigo(j.idJugador, mi_rol)
            dist = juego.distancia(jugador.idJugador, j.idJugador)
            alcance = jugador.distancia  # distancia de disparo del arma
            if p_enemigo > UMBRAL_ENEMIGO and dist <= alcance:
                resultado.append(j)
        return resultado

    def _mira_telescopica_util(self, jugador, juego):
        """True si equipar la Mira Telescópica (–1 distancia) metería a algún
        enemigo, hoy justo fuera de mi alcance, dentro de él."""
        mi_rol = jugador.rol
        alcance = jugador.distancia
        for j in juego.jugadores:
            if j.muerto or j.idJugador == jugador.idJugador:
                continue
            if self.prob_enemigo(j.idJugador, mi_rol) <= UMBRAL_ENEMIGO:
                continue
            if juego.distancia(jugador.idJugador, j.idJugador) == alcance + 1:
                return True
        return False

    def _mejor_objetivo_carcel(self, jugador, juego):
        """Rival peligroso y sin cárcel al que neutralizar aunque esté fuera del
        alcance de mi arma (la Cárcel no requiere distancia). Devuelve None si
        no hay ningún candidato claro. No se puede encarcelar al Sheriff.
        """
        mi_rol = jugador.rol
        bando_fuerte = None
        if mi_rol == 'Renegado':
            fuerza_sheriff, fuerza_forajido = self._fuerza_bandos(jugador, juego)
            bando_fuerte = 'Sheriff' if fuerza_sheriff >= fuerza_forajido else 'Forajido'
        mejor = None
        mejor_score = UMBRAL_ENEMIGO * 10  # mismo umbral que _enemigos_al_alcance
        for j in juego.jugadores:
            if j.muerto or j.idJugador == jugador.idJugador or j.rol == 'Sheriff':
                continue
            if getattr(j, 'carcel', False):
                continue
            score = self.prob_enemigo(j.idJugador, mi_rol) * 10
            if mi_rol in ('Sheriff', 'Ayudante'):
                score += self.amenaza_sheriff.get(j.idJugador, 0) * 8
            if bando_fuerte is not None:
                c = self.creencias.get(j.idJugador, {})
                if bando_fuerte == 'Sheriff':
                    score += (c.get('Sheriff', 0) + c.get('Ayudante', 0)) * 10
                else:
                    score += c.get('Forajido', 0) * 10
            if score > mejor_score:
                mejor = j
                mejor_score = score
        return mejor
