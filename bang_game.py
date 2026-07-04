import csv
import random

from ClasesAux import Carta, Personaje, Jugador

DESCRIPCIONES_PERSONAJE = {
    "Bart Cassidy": "Roba 1 carta cada vez que pierde una vida.",
    "Black Jack": "Muestra su 2ª carta al robar: si es ♥/♦ roba una carta extra.",
    "Calamity Janet": "Puede usar Bang como Fallaste y viceversa.",
    "El Gringo": "Cuando pierde una vida, roba 1 carta al azar del atacante.",
    "Jesse Jones": "Puede robar su 1ª carta de la mano de un rival en vez del mazo.",
    "Jourdonnais": "Tiene un Barril innato: siempre puede intentar esquivar con barril.",
    "Kit Carlson": "Roba 3 cartas al inicio del turno y devuelve 1 al mazo.",
    "Lucky Duke": "En cada chequeo roba 2 cartas y elige cuál usar.",
    "Paul Regret": "Todos los rivales ven su distancia incrementada en 1.",
    "Pedro Ramirez": "Puede coger la carta superior del descarte en vez de robar del mazo.",
    "Rose Doolan": "Ve a todos los jugadores a distancia 1 menos de la real.",
    "Sid Ketchum": "Puede descartar 2 cartas para recuperar 1 vida (en su turno o al morir).",
    "Slab the Killer": "Sus rivales necesitan 2 Fallaste para esquivar su Bang.",
    "Suzy Lafayette": "Cuando se queda sin cartas en mano, roba 1 automáticamente.",
    "Willy the Kid": "Puede jugar tantos Bang como quiera por turno.",
}

DISTANCIAS_ARMA = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


class ConsoleIO:
    """Simple console-based IO adapter providing a `prompt` method.
    The game logic will call `io.prompt(text, options=None)`; if `options` is a list,
    the returned value will be one of the options (as string). If `options` is None,
    it will return the raw input string.
    """

    def prompt(self, text, options=None):
        if options:
            opts_str = "/".join(str(o) for o in options)
            while True:
                res = input(f"{text} [{opts_str}]: ").strip()
                if res in options:
                    return res
                # allow case-insensitive matches for common choices
                up = res.upper()
                for o in options:
                    if isinstance(o, str) and up == o.upper():
                        return o
                print("Opción no válida, inténtalo de nuevo.")
        else:
            return input(text)

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        options = (["FIN"] if permitir_fin else []) + (["PODER"] if permitir_poder else []) + list(opciones)
        return self.prompt(text, options=options)

    def elegir_personaje(self, nombre_jugador, rol, personaje_a, personaje_b):
        desc_a = DESCRIPCIONES_PERSONAJE.get(personaje_a.nombre, "Sin descripción")
        desc_b = DESCRIPCIONES_PERSONAJE.get(personaje_b.nombre, "Sin descripción")
        prompt_text = (
            f"{nombre_jugador}, eres {rol}. ¿Qué personaje prefieres?\n"
            f"  A: {personaje_a.nombre} ({personaje_a.vidas} vidas) — {desc_a}\n"
            f"  B: {personaje_b.nombre} ({personaje_b.vidas} vidas) — {desc_b}"
        )
        eleccion = self.prompt(prompt_text, options=["A", "B"]).strip().upper()
        return personaje_a if eleccion == "A" else personaje_b

    def elegir_jugador(self, jugadores, text, jugadores_fuera_alcance=None):
        opciones = {str(j.idJugador + 1): j.idJugador for j in jugadores}
        texto = text + "\n" + "\n".join(f"{j.idJugador + 1} - {j.nombre}" for j in jugadores)
        if jugadores_fuera_alcance:
            texto += "\nFuera de alcance: " + ", ".join(j.nombre for j in jugadores_fuera_alcance)
        eleccion = self.prompt(texto, options=list(opciones.keys()))
        return opciones[eleccion]

    def elegir_carta_rival(self, rival, text):
        elementos = [("mano", i) for i in range(len(rival.cartasMano))]
        elementos += [("equipo", i) for i in range(len(rival.cartasEquipadas))]
        etiquetas = []
        for n, (origen, i) in enumerate(elementos, start=1):
            if origen == "mano":
                etiquetas.append(f"{n} - Carta oculta de la mano")
            else:
                etiquetas.append(f"{n} - {rival.cartasEquipadas[i].nombre} (equipada)")
        texto = text + "\n" + "\n".join(etiquetas)
        opciones = [str(i + 1) for i in range(len(elementos))]
        eleccion = self.prompt(texto, options=opciones)
        return elementos[int(eleccion) - 1]

    def elegir_lucky_duke(self, jugador, carta1, carta2):
        """Lucky Duke elige cuál de las 2 cartas usar para el chequeo."""
        texto = (f"{jugador.nombre} (Lucky Duke): elige el resultado del desenfunde:\n"
                 f"1 - {carta1.nombre} ({carta1.palo} {carta1.numero})\n"
                 f"2 - {carta2.nombre} ({carta2.palo} {carta2.numero})")
        eleccion = self.prompt(texto, options=["1", "2"])
        return carta1 if eleccion == "1" else carta2

    def elegir_robo_jesse(self, jugador, rivales):
        """Devuelve idJugador del rival a robar, o None para robar del mazo."""
        if not rivales:
            return None
        opciones = {str(j.idJugador + 1): j.idJugador for j in rivales}
        opciones["0"] = None
        texto = (f"{jugador.nombre} (Jesse Jones): ¿robas la 1ª carta de un rival o del mazo?\n"
                 "0 - Del mazo\n" +
                 "\n".join(f"{j.idJugador + 1} - {j.nombre}" for j in rivales))
        eleccion = self.prompt(texto, options=list(opciones.keys()))
        return opciones[eleccion]

    def elegir_robo_pedro(self, jugador, carta_top):
        """Devuelve True si quiere coger la carta del descarte, False para el mazo."""
        texto = (f"{jugador.nombre} (Pedro Ramírez): la carta top del descarte es "
                 f"{carta_top.nombre} ({carta_top.palo} {carta_top.numero}). ¿La coges?")
        return self.prompt(texto, options=["SI", "NO"]).strip().upper() == "SI"

    def elegir_kit_carlson(self, jugador, cartas):
        """Devuelve el índice (0-based) de la carta que Kit Carlson devuelve al mazo."""
        etiquetas = [f"{i + 1} - {c.nombre} ({c.palo} {c.numero})" for i, c in enumerate(cartas)]
        texto = (f"{jugador.nombre} (Kit Carlson): elige la carta a devolver al mazo:\n"
                 + "\n".join(etiquetas))
        eleccion = self.prompt(texto, options=["1", "2", "3"])
        return int(eleccion) - 1

    def elegir_almacen_carta(self, jugador, cartas):
        etiquetas = [f"{i + 1} - {c.nombre} ({c.palo} {c.numero})" for i, c in enumerate(cartas)]
        texto = f"{jugador.nombre}, elige una carta del Almacén:\n" + "\n".join(etiquetas)
        opciones = [str(i + 1) for i in range(len(cartas))]
        eleccion = self.prompt(texto, options=opciones)
        return int(eleccion) - 1


def info_extract(cartas_csv, personajes_csv, roles_csv):
    """Carga y devuelve el mazo, la lista de personajes y la lista de roles desde sus archivos.

    Lee cartas.csv (id_clase;nombre;tipo;cantidad), personajes.txt (id;nombre;vidas)
    y roles.txt (un rol por línea). Las cartas reciben palo y número aleatorios al crearse.

    Args:
        cartas_csv (str): Ruta al CSV de cartas.
        personajes_csv (str): Ruta al fichero de personajes.
        roles_csv (str): Ruta al fichero de roles.

    Returns:
        tuple[list[Carta], list[Personaje], list[str]]:
            (baraja barajada, lista de personajes, lista de roles en orden de turno)
    """
    baraja = []
    with open(cartas_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        id_objeto = 0
        for row in reader:
            if not row:
                continue
            id_clase = int(row[0])
            nombre = row[1]
            tipo = row[2]
            cantidad = int(row[3])
            for _ in range(cantidad):
                carta = Carta(id_objeto, id_clase, nombre, tipo)
                carta.numero = random.randint(1, 13)
                carta.palo = random.choice(["Corazones", "Diamantes", "Picas", "Treboles"])
                baraja.append(carta)
                id_objeto += 1

    random.shuffle(baraja)

    personajes = []
    with open(personajes_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if not row:
                continue
            personajes.append(Personaje(int(row[0]), row[1].strip(), int(row[2])))

    roles = []
    with open(roles_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if row:
                roles.append(row[0])

    return baraja, personajes, roles


def create_players(num_players, player_names, personajes, roles, io=None):
    """Crea y devuelve la lista de jugadores con roles y personajes asignados.

    A cada jugador se le asigna un rol al azar (de entre los roles para ese número
    de jugadores) y elige entre dos personajes presentados aleatoriamente.

    Args:
        num_players (int): Número de jugadores (4-7).
        player_names (list[str]): Nombres de los jugadores en orden de turno.
        personajes (list[Personaje]): Pool completo de personajes disponibles.
        roles (list[str]): Lista de roles leída de roles.txt (todos, para todos los n).
        io: Adaptador IO para solicitar la elección de personaje. Por defecto ConsoleIO.

    Returns:
        list[Jugador]: Jugadores inicializados, sin cartas en mano aún.

    Raises:
        ValueError: Si num_players no está en {4, 5, 6, 7}.
        RuntimeError: Si no hay suficientes personajes en el pool.
    """
    if num_players not in {4, 5, 6, 7}:
        raise ValueError("Solo existen los modos 4, 5, 6, 7 jugadores")

    personajes_disponibles = personajes.copy()
    random.shuffle(personajes_disponibles)
    roles_disponibles = roles[:num_players]
    random.shuffle(roles_disponibles)

    jugadores = []
    for id_jugador, nombre in enumerate(player_names):
        if len(personajes_disponibles) < 2:
            raise RuntimeError("No hay personajes suficientes para elegir")
        personaje_a = personajes_disponibles.pop()
        personaje_b = personajes_disponibles.pop()
        rol = roles_disponibles.pop()

        io = io or ConsoleIO()
        personaje = io.elegir_personaje(nombre, rol, personaje_a, personaje_b)

        jugador = Jugador(id_jugador, nombre, personaje, rol, [])
        jugadores.append(jugador)

    return jugadores


class Juego:
    """Motor principal de la partida de BANG!

    Gestiona el estado global (mazo, montón de descartes, turno, victoria)
    y contiene toda la lógica de las cartas y mecánicas de juego.

    Attributes:
        jugadores (list[Jugador]): Lista de jugadores en orden de turno (índice == idJugador).
        baraja (list[Carta]): Mazo de robo. Se rebaraja de monton_descartes cuando se vacía.
        monton_descartes (list[Carta]): Pila de descartes. La última carta es visible.
        ronda (int): Número de ronda actual (se incrementa cada vez que el Sheriff juega).
        turno (int): Índice del SIGUIENTE jugador en jugar (se usa % n al inicio de cada iter).
        io: Adaptador IO activo (ConsoleIO, FlaskIO o PygameIO).
        game_over (bool): True en cuanto se cumple una condición de victoria.
        ganador (str): Rol ganador ("Sheriff", "Forajidos" o "Renegado"). None hasta game_over.
    """

    def __init__(self, jugadores, baraja, io=None):
        self.jugadores = jugadores
        self.baraja = baraja
        self.ronda = 0
        self.turno = 0
        self.jugadores_eliminados = []
        self.monton_descartes = []
        self.io = io or ConsoleIO()
        self.game_over = False
        self.ganador = None
        self.repartir_cartas_inicio()

    def __str__(self):
        datos = f"DATOS DE LA PARTIDA\n-RONDA Nº {self.ronda}\n-TURNO Nº {self.turno}"
        jugadores_str = "\n -------------------------------------\n JUGADORES \n"
        for jugador in self.jugadores:
            jugadores_str += str(jugador)
        return datos + jugadores_str

    def repartir_cartas_inicio(self):
        """Reparte 5 cartas iniciales a cada jugador al comienzo de la partida."""
        for jugador in self.jugadores:
            for _ in range(5):
                jugador.recibeCarta(self._draw_from_deck())

    def _draw_from_deck(self):
        """Saca y devuelve la carta superior de la baraja, rebarajando el descarte si es necesario."""
        if not self.baraja:
            self._barajar_monton()
        if not self.baraja:
            raise RuntimeError("No quedan cartas en la baraja")
        return self.baraja.pop()

    def _barajar_monton(self):
        """Baraja el montón de descartes y lo convierte en la nueva baraja de robo."""
        if not self.monton_descartes:
            return
        random.shuffle(self.monton_descartes)
        self.baraja = self.monton_descartes
        self.monton_descartes = []

    def _discard_card(self, carta):
        """Envía una carta directamente al montón de descartes."""
        self.monton_descartes.append(carta)

    def recibe_carta(self, id_jugador):
        """El jugador roba la carta superior del mazo y la añade a su mano."""
        carta = self._draw_from_deck()
        self.jugadores[id_jugador].recibeCarta(carta)

    def perder_carta(self, id_jugador, id_carta):
        """Retira una carta de la mano del jugador y la descarta. Activa el hook de mano vacía."""
        carta = self.jugadores[id_jugador].getCarta(id_carta)
        self.jugadores[id_jugador].pierdeCarta(id_carta)
        self._discard_card(carta)
        self._hook_mano_vacia(id_jugador)

    def _hook_mano_vacia(self, id_jugador):
        """Suzy Lafayette: roba 1 carta al quedarse sin cartas en mano."""
        jugador = self.jugadores[id_jugador]
        if jugador.personaje.nombre == "Suzy Lafayette" and not jugador.cartasMano:
            self.recibe_carta(id_jugador)
            print(f"{jugador.nombre} (Suzy Lafayette) roba 1 carta al quedarse sin cartas.")

    def quitar_de_mano(self, id_jugador, id_carta):
        """Quita una carta de la mano sin descartarla (para equiparla a un jugador)."""
        carta = self.jugadores[id_jugador].getCarta(id_carta)
        self.jugadores[id_jugador].pierdeCarta(id_carta)
        return carta

    def robar_carta_mano(self, id_origen, id_carta_origen, id_destino):
        """Mueve una carta de la mano de id_origen a la mano de id_destino."""
        carta = self.quitar_de_mano(id_origen, id_carta_origen)
        self.jugadores[id_destino].recibeCarta(carta)
        return carta

    def quitar_carta_equipada(self, id_jugador, indice):
        """Quita una carta equipada (arma u objeto en juego) y revierte su efecto."""
        jugador = self.jugadores[id_jugador]
        carta = jugador.pierdeCartaEquipada(indice)
        clase = carta.idClase
        if clase in {1, 2, 3, 4, 5}:
            jugador.cambioArma(0, 1)
            if clase == 1:
                jugador.quitarVolcanic()
        elif clase == 6:
            jugador.quitarCarcel()
        elif clase == 7:
            jugador.quitarMustang()
        elif clase == 8:
            jugador.quitarBarril()
        elif clase == 9:
            jugador.quitarDinamita()
        elif clase == 10:
            jugador.quitarMiraTelescopica()
        return carta

    def _limpiar_jugador_muerto(self, id_jugador):
        """Descarta todas las cartas del jugador muerto y revela su rol."""
        jugador = self.jugadores[id_jugador]
        print(f"\n💀 {jugador.nombre} ha sido eliminado. Era {jugador.rol}.\n")
        for carta in jugador.cartasMano[:]:
            self._discard_card(carta)
        jugador.cartasMano.clear()
        while jugador.cartasEquipadas:
            carta = jugador.cartasEquipadas.pop()
            self._discard_card(carta)
        jugador.arma = 0
        jugador.distancia = 1
        jugador.mustang = False
        jugador.barril = False
        jugador.dinamita = False
        jugador.carcel = False
        jugador.miraTelescopica = False
        jugador.volcanic = False

    def comprobar_victoria(self):
        """Comprueba las condiciones de victoria y actualiza game_over/ganador."""
        vivos = [j for j in self.jugadores if not j.muerto]
        sheriff = next((j for j in self.jugadores if j.rol == "Sheriff"), None)

        # Renegado último superviviente
        if len(vivos) == 1 and vivos[0].rol == "Renegado":
            self.game_over = True
            self.ganador = "Renegado"
            print(f"\n🏆 ¡{vivos[0].nombre} (Renegado) gana la partida!\n")
            return

        # Sheriff muerto → ganan Forajidos
        if sheriff and sheriff.muerto:
            self.game_over = True
            self.ganador = "Forajidos"
            print("\n🏆 ¡Los Forajidos ganan la partida! El Sheriff ha caído.\n")
            return

        # Todos los Forajidos y Renegado eliminados → gana Sheriff + Ayudantes
        enemigos_sheriff = [j for j in self.jugadores if j.rol in {"Forajido", "Renegado"}]
        if all(j.muerto for j in enemigos_sheriff):
            self.game_over = True
            self.ganador = "Sheriff"
            print("\n🏆 ¡El Sheriff y sus Ayudantes ganan la partida!\n")

    def _on_muerte(self, id_jugador, id_atacante=None):
        """Gestiona la muerte de un jugador: limpieza, reglas especiales y victoria."""
        jugador = self.jugadores[id_jugador]
        if not jugador.muerto:
            return

        # Buitre Sam: se queda con todas las cartas del muerto antes de limpiar
        sam = next((j for j in self.jugadores if j.personaje.nombre == '"Buitre" Sam' and not j.muerto), None)
        if sam and sam.idJugador != id_jugador:
            print(f"\n🦅 {sam.nombre} (Buitre Sam) roba todas las cartas de {jugador.nombre}.\n")
            for carta in jugador.cartasMano[:]:
                sam.recibeCarta(carta)
            jugador.cartasMano.clear()
            for carta in jugador.cartasEquipadas[:]:
                sam.recibeCarta(carta)
            jugador.cartasEquipadas.clear()

        self._limpiar_jugador_muerto(id_jugador)

        if id_atacante is not None:
            atacante = self.jugadores[id_atacante]

            # Sheriff mata a un Ayudante → descarta mano y cartas equipadas
            if atacante.rol == "Sheriff" and jugador.rol == "Ayudante":
                print(f"\n⚠️  {atacante.nombre} (Sheriff) ha matado a su Ayudante y descarta todas sus cartas.\n")
                for carta in atacante.cartasMano[:]:
                    self._discard_card(carta)
                atacante.cartasMano.clear()
                while atacante.cartasEquipadas:
                    self._discard_card(self.quitar_carta_equipada(id_atacante, 0))

            # Cualquier jugador elimina a un Forajido → roba 3 cartas de recompensa
            if jugador.rol == "Forajido":
                print(f"\n🎁 {atacante.nombre} ha eliminado a un Forajido y roba 3 cartas de recompensa.\n")
                for _ in range(3):
                    self.recibe_carta(id_atacante)

        self.comprobar_victoria()

    def poder_disponible(self, id_jugador):
        """Devuelve True si el jugador puede activar su poder especial ahora."""
        jugador = self.jugadores[id_jugador]
        nombre = jugador.personaje.nombre
        if nombre == "Sid Ketchum":
            return len(jugador.cartasMano) >= 2 and jugador.vidas < jugador.vidasMax
        return False

    def usar_poder(self, id_jugador):
        """Activa el poder especial del jugador."""
        jugador = self.jugadores[id_jugador]
        nombre = jugador.personaje.nombre
        if nombre == "Sid Ketchum":
            self.sid_ketchum(id_jugador)

    def sid_ketchum(self, id_jugador):
        """Sid Ketchum descarta 2 cartas para ganar 1 vida. Repetible mientras tenga cartas."""
        jugador = self.jugadores[id_jugador]
        jugador_anterior = getattr(self.io, 'current_jugador', None)
        if hasattr(self.io, 'current_jugador'):
            self.io.current_jugador = jugador
        try:
            while jugador.vidas < jugador.vidasMax and len(jugador.cartasMano) >= 2:
                respuesta = self.io.prompt(
                    f"{jugador.nombre} (Sid Ketchum): ¿Descartas 2 cartas para ganar 1 vida? ({jugador.vidas}/{jugador.vidasMax})",
                    options=["SI", "NO"],
                ).strip().upper()
                if respuesta != "SI":
                    break
                for _ in range(2):
                    opciones = [str(i + 1) for i in range(len(jugador.cartasMano))]
                    eleccion = self.io.elegir_carta(jugador, "Elige una carta para descartar.", opciones, permitir_fin=False)
                    indice = int(eleccion) - 1
                    self.perder_carta(id_jugador, indice)
                jugador.ganarVida()
                print(f"{jugador.nombre} usa su poder y gana 1 vida ({jugador.vidas}/{jugador.vidasMax}).")
        finally:
            if hasattr(self.io, 'current_jugador'):
                self.io.current_jugador = jugador_anterior

    def _ofrecer_cerveza(self, id_jugador):
        """Permite usar Cervezas para sobrevivir cuando se llega a 0 vidas.
        No se puede usar si solo quedan 2 jugadores en la partida.
        """
        jugador = self.jugadores[id_jugador]
        vivos = len([j for j in self.jugadores if not j.muerto])
        if vivos <= 2:
            return

        jugador_anterior = getattr(self.io, 'current_jugador', None)
        if hasattr(self.io, 'current_jugador'):
            self.io.current_jugador = jugador
        try:
            while jugador.vidas <= 0:
                # Sid Ketchum puede usar su poder para sobrevivir
                if jugador.personaje.nombre == "Sid Ketchum" and len(jugador.cartasMano) >= 2:
                    self.sid_ketchum(id_jugador)
                    if jugador.vidas > 0:
                        break
                tiene, indice = self._buscar_carta_por_clase(jugador, 13)
                if not tiene:
                    break
                respuesta = self.io.prompt(
                    f"{jugador.nombre}, vas a morir. ¿Usas una Cerveza para sobrevivir?",
                    options=["SI", "NO"],
                ).strip().upper()
                if respuesta != "SI":
                    break
                self.perder_carta(id_jugador, indice)
                jugador.ganarVida()
                print(f"{jugador.nombre} usa una Cerveza y sobrevive con {jugador.vidas} vida(s).")
        finally:
            if hasattr(self.io, 'current_jugador'):
                self.io.current_jugador = jugador_anterior

    def _hook_pierde_vida(self, id_jugador, id_atacante):
        """Efectos de personaje que se disparan tras perder 1 vida."""
        jugador = self.jugadores[id_jugador]

        # Bart Cassidy: roba 1 carta cada vez que pierde una vida
        if jugador.personaje.nombre == "Bart Cassidy":
            self.recibe_carta(id_jugador)
            print(f"{jugador.nombre} (Bart Cassidy) roba 1 carta.")

        # El Gringo: roba 1 carta al azar del atacante (solo si fue un jugador, no dinamita)
        if jugador.personaje.nombre == "El Gringo" and id_atacante is not None:
            atacante = self.jugadores[id_atacante]
            if atacante.cartasMano:
                indice = random.randint(0, len(atacante.cartasMano) - 1)
                carta = atacante.cartasMano[indice]
                atacante.pierdeCarta(indice)
                jugador.recibeCarta(carta)
                print(f"{jugador.nombre} (El Gringo) roba {carta.nombre} de la mano de {atacante.nombre}.")
            else:
                print(f"{jugador.nombre} (El Gringo) quería robar pero {atacante.nombre} no tiene cartas.")

    def infligir_dano(self, id_jugador, cantidad=1, id_atacante=None):
        """Inflige `cantidad` puntos de daño y gestiona la muerte si ocurre."""
        jugador = self.jugadores[id_jugador]
        for _ in range(cantidad):
            jugador.perderVida()
            self._hook_pierde_vida(id_jugador, id_atacante)
            if jugador.muerto:
                jugador.muerto = False
                self._ofrecer_cerveza(id_jugador)
                if jugador.vidas <= 0:
                    jugador.muerto = True
                    break
        if jugador.muerto:
            self._on_muerte(id_jugador, id_atacante)

    def distancia(self, id_jugador_a, id_jugador_b):
        """Calcula la distancia entre dos jugadores desde el punto de vista de A.

        La distancia base es el menor número de jugadores vivos que hay entre ambos,
        contando hacia la izquierda o hacia la derecha (la mesa es un ciclo).
        Después se aplican los modificadores asimétricos: la Mira Telescópica de A
        resta 1 y el Mustang de B suma 1. El resultado mínimo es 1.
        """
        if id_jugador_a == id_jugador_b:
            return 0

        jugador_a = self.jugadores[id_jugador_a]
        jugador_b = self.jugadores[id_jugador_b]

        vivos = sorted(
            (j for j in self.jugadores if not j.muerto or j.idJugador in (id_jugador_a, id_jugador_b)),
            key=lambda j: j.idJugador,
        )
        n = len(vivos)
        pos_a = next(i for i, j in enumerate(vivos) if j.idJugador == id_jugador_a)
        pos_b = next(i for i, j in enumerate(vivos) if j.idJugador == id_jugador_b)

        diferencia = abs(pos_a - pos_b)
        distancia_mesa = min(diferencia, n - diferencia)

        if jugador_a.miraTelescopica or jugador_a.personaje.nombre == "Rose Doolan":
            distancia_mesa -= 1
        if jugador_b.mustang or jugador_b.personaje.nombre == "Paul Regret":
            distancia_mesa += 1

        return max(1, distancia_mesa)

    def elegir_rival(self, id_jugador, requiere_alcance=False):
        """Pide al jugador que seleccione un rival y devuelve su idJugador.

        Args:
            id_jugador (int): Jugador que elige.
            requiere_alcance (bool): Si True, solo presenta rivales dentro del rango del arma.

        Returns:
            int | None: idJugador del rival elegido, o None si no hay rivales válidos.
        """
        rivales = [j for j in self.jugadores if j.idJugador != id_jugador and not j.muerto]
        if not rivales:
            return None

        if not requiere_alcance:
            return self.io.elegir_jugador(rivales, "Selecciona un jugador rival haciendo clic en su panel.")

        jugador = self.jugadores[id_jugador]
        alcanzables = [r for r in rivales if jugador.distancia >= self.distancia(id_jugador, r.idJugador)]
        fuera_alcance = [r for r in rivales if r not in alcanzables]
        if not alcanzables:
            return None
        return self.io.elegir_jugador(
            alcanzables, "Selecciona un jugador rival haciendo clic en su panel.",
            jugadores_fuera_alcance=fuera_alcance,
        )
    def elegir_carta_rival(self, id_jugador, id_rival):
        """Pide al jugador que elija una carta (mano u equipada) del rival para robársela.

        Returns:
            tuple[str, int] | None: ("mano"|"equipo", índice) o None si el rival no tiene cartas.
        """
        rival = self.jugadores[id_rival]
        if not rival.cartasMano and not rival.cartasEquipadas:
            return None
        return self.io.elegir_carta_rival(rival, f"Elige una carta de {rival.nombre} para robarla.")
    def _buscar_carta_por_clase(self, jugador, id_clase):
        """Busca la primera carta con idClase dado en la mano del jugador.

        Returns:
            tuple[bool, int]: (encontrada, índice). Si no existe, índice = -1.
        """
        for indice, carta in enumerate(jugador.cartasMano):
            if carta.idClase == id_clase:
                return True, indice
        return False, -1

    def respuesta(self, id_rival, id_clase_respuesta):
        """Pregunta al rival si quiere responder a un ataque con Bang (11) o Fallaste (12).

        Gestiona Calamity Janet (puede usar Bang como Fallaste). Cambia temporalmente
        current_jugador en el IO para que la interfaz muestre la mano del rival.

        Args:
            id_rival (int): Jugador que debe responder.
            id_clase_respuesta (int): 11 = necesita Bang (Duelo/Indios), 12 = necesita Fallaste (Bang).

        Returns:
            bool: True si el rival esquivó el ataque con éxito.
        """
        rival = self.jugadores[id_rival]
        if id_clase_respuesta not in {11, 12}:
            return False

        nombre_pregunta = {
            11: "BANG",
            12: "FALLASTE",
        }
        prompt_text = f"{rival.nombre}, te han atacado. ¿Quieres usar un {nombre_pregunta[id_clase_respuesta]}?"

        # Muestra la mano del rival mientras decide, y restaura la del jugador activo después.
        jugador_anterior = getattr(self.io, 'current_jugador', None)
        if hasattr(self.io, 'current_jugador'):
            self.io.current_jugador = rival
        try:
            respuesta = self.io.prompt(prompt_text, options=["SI", "NO"]).strip().upper()
        finally:
            if hasattr(self.io, 'current_jugador'):
                self.io.current_jugador = jugador_anterior

        if respuesta != "SI":
            return False

        # Calamity Janet puede usar Bang como Fallaste
        clases_validas = [id_clase_respuesta]
        if id_clase_respuesta == 12 and rival.personaje.nombre == "Calamity Janet":
            clases_validas.append(11)

        for clase in clases_validas:
            tiene, indice = self._buscar_carta_por_clase(rival, clase)
            if tiene:
                self.perder_carta(id_rival, indice)
                return True
        return False

    def anadir_arma(self, id_jugador, id_carta):
        """Equipa un arma al jugador, descartando el arma anterior si la hay.

        Actualiza arma, rango de ataque y activa/desactiva el flag Volcanic.
        """
        jugador = self.jugadores[id_jugador]
        for i, c in enumerate(jugador.cartasEquipadas):
            if c.idClase in {1, 2, 3, 4, 5}:
                carta_vieja = self.quitar_carta_equipada(id_jugador, i)
                self._discard_card(carta_vieja)
                break
        carta = self.quitar_de_mano(id_jugador, id_carta)
        distancia = DISTANCIAS_ARMA.get(carta.idClase, 1)
        jugador.cambioArma(carta.idClase, distancia)
        if carta.idClase == 1:
            jugador.ponerVolcanic()
        jugador.equipaCarta(carta)

    def poner_carcel(self, id_jugador, id_enemigo, id_carta):
        """Equipa una Cárcel al rival. No se puede encarcelar al Sheriff ni a alguien ya encarcelado."""
        if id_enemigo is None:
            print("No hay ningún rival al que poner la cárcel")
            return
        if self.jugadores[id_enemigo].rol == "Sheriff":
            print("Regla: no se puede meter al Sheriff en la cárcel")
            return
        if self.jugadores[id_enemigo].carcel:
            print("No puedes poner más cárceles a este jugador")
            return
        carta = self.quitar_de_mano(id_jugador, id_carta)
        self.jugadores[id_enemigo].ponerCarcel()
        self.jugadores[id_enemigo].equipaCarta(carta)
    def poner_dinamita(self, id_jugador, id_carta):
        """Equipa una Dinamita al jugador. Solo puede haber una por jugador."""
        jugador = self.jugadores[id_jugador]
        if jugador.dinamita:
            print("Ya tienes una Dinamita equipada")
            return
        carta = self.quitar_de_mano(id_jugador, id_carta)
        jugador.ponerDinamita()
        jugador.equipaCarta(carta)

    def bang(self, id_jugador, id_enemigo, id_carta):
        """Juega un Bang contra el enemigo elegido.

        Respeta el límite de 1 Bang/turno (salvo Volcanic o Willy the Kid).
        Gestiona el intento de esquivar con Barril (Jourdonnais incluido)
        y la respuesta con Fallaste. Slab the Killer requiere 2 Fallaste para esquivar.
        """
        if id_enemigo is None:
            print("No hay ningún rival al alcance")
            return
        jugador = self.jugadores[id_jugador]
        enemigo = self.jugadores[id_enemigo]
        willy = jugador.personaje.nombre == "Willy the Kid"
        if jugador.contBang == 0 or jugador.volcanic or willy:
            self.perder_carta(id_jugador, id_carta)
            jugador.contBang += 1

            slab = jugador.personaje.nombre == "Slab the Killer"
            fallastes_necesarios = 2 if slab else 1
            fallastes_conseguidos = 0

            tiene_barril_innato = enemigo.personaje.nombre == "Jourdonnais"
            intentos_barril = 0
            if enemigo.barril:
                intentos_barril += 1
            if tiene_barril_innato:
                intentos_barril += 1

            for intento in range(intentos_barril):
                if fallastes_conseguidos >= fallastes_necesarios:
                    break
                print(f"{enemigo.nombre} intenta esquivar con el barril (intento {intento + 1}/{intentos_barril})")
                carta = self._desenfundar(id_enemigo)
                if carta.palo == "Corazones":
                    fallastes_conseguidos += 1
                    print(f"{enemigo.nombre} saca {carta.nombre} de Corazones — barril esquiva (Fallaste {fallastes_conseguidos}/{fallastes_necesarios}).")
                else:
                    print(f"{enemigo.nombre} saca {carta.nombre} y el barril no esquiva.")

            while fallastes_conseguidos < fallastes_necesarios:
                if not self.respuesta(id_enemigo, 12):
                    break
                fallastes_conseguidos += 1

            if fallastes_conseguidos >= fallastes_necesarios:
                print("¡Pero has fallado!")
            else:
                self.infligir_dano(id_enemigo, id_atacante=id_jugador)
        else:
            print("No puedes hacer más BANGs")

    def duelo(self, id_jugador, id_enemigo, id_carta):
        """Juega un Duelo: los jugadores se alternan usando Bang hasta que uno no pueda. Pierde 1 vida."""
        if id_enemigo is None:
            print("No hay ningún rival al que retar a un duelo")
            return
        self.perder_carta(id_jugador, id_carta)
        turno_actual = id_enemigo
        turno_rival = id_jugador
        while self.respuesta(turno_actual, 11):
            turno_actual, turno_rival = turno_rival, turno_actual
        id_perdedor = turno_actual
        id_ganador_duelo = turno_rival
        self.infligir_dano(id_perdedor, id_atacante=id_ganador_duelo)

    def ametralladora(self, id_jugador, id_carta):
        """Juega una Ametralladora: todos los rivales deben usar un Fallaste o pierden 1 vida."""
        self.perder_carta(id_jugador, id_carta)
        for enemigo in self.jugadores:
            if enemigo.idJugador != id_jugador and not enemigo.muerto:
                respuesta = self.respuesta(enemigo.idJugador, 12)
                if not respuesta:
                    self.infligir_dano(enemigo.idJugador, id_atacante=id_jugador)

    def indios(self, id_jugador, id_carta):
        """Juega Indios: todos los rivales deben usar un Bang o pierden 1 vida."""
        self.perder_carta(id_jugador, id_carta)
        for enemigo in self.jugadores:
            if enemigo.idJugador != id_jugador and not enemigo.muerto:
                respuesta = self.respuesta(enemigo.idJugador, 11)
                if not respuesta:
                    self.infligir_dano(enemigo.idJugador, id_atacante=id_jugador)

    def cerveza(self, id_jugador, id_carta):
        """Juega una Cerveza: recupera 1 vida. Sin efecto si quedan ≤2 jugadores vivos."""
        jugador = self.jugadores[id_jugador]
        vivos = sum(1 for j in self.jugadores if not j.muerto)
        if vivos <= 2:
            print("Regla: la Cerveza no tiene efecto con solo 2 jugadores")
            return
        if jugador.vidas >= jugador.vidasMax:
            print("Ya tienes el máximo de vida")
            return
        jugador.ganarVida()
        self.perder_carta(id_jugador, id_carta)
    
    def saloon(self, id_jugador, id_carta):
        """Juega el Saloon: todos los jugadores vivos recuperan 1 vida."""
        self.perder_carta(id_jugador, id_carta)
        for jugador in self.jugadores:
            if not jugador.muerto:
                jugador.ganarVida()

    def mustang(self, id_jugador, id_carta):
        """Equipa el Mustang: los rivales ven la distancia a este jugador aumentada en 1."""
        jugador = self.jugadores[id_jugador]
        if jugador.mustang:
            print("Ya tienes un Mustang")
            return
        carta = self.quitar_de_mano(id_jugador, id_carta)
        jugador.ponerMustang()
        jugador.equipaCarta(carta)

    def barril(self, id_jugador, id_carta):
        """Equipa el Barril: al recibir un Bang, intenta esquivar automáticamente robando con ♥."""
        jugador = self.jugadores[id_jugador]
        if jugador.barril:
            print("Ya tienes un Barril")
            return
        carta = self.quitar_de_mano(id_jugador, id_carta)
        jugador.ponerBarril()
        jugador.equipaCarta(carta)

    def mira_telescopica(self, id_jugador, id_carta):
        """Equipa la Mira Telescópica: reduce en 1 la distancia de ataque del jugador."""
        jugador = self.jugadores[id_jugador]
        if jugador.miraTelescopica:
            print("Ya tienes una Mira Telescópica")
            return
        carta = self.quitar_de_mano(id_jugador, id_carta)
        jugador.ponerMiraTelescopica()
        jugador.equipaCarta(carta)

    def almacen(self, id_jugador, id_carta):
        """Juega el Almacén: reparte N cartas boca arriba (N = jugadores vivos); cada jugador elige 1 en orden."""
        self.perder_carta(id_jugador, id_carta)
        vivos = [j for j in self.jugadores if not j.muerto]
        cartas_mesa = [self._draw_from_deck() for _ in range(len(vivos))]

        n = len(self.jugadores)
        orden = [self.jugadores[(id_jugador + i) % n] for i in range(n) if not self.jugadores[(id_jugador + i) % n].muerto]

        jugador_anterior = getattr(self.io, 'current_jugador', None)
        try:
            for jugador in orden:
                if hasattr(self.io, 'current_jugador'):
                    self.io.current_jugador = jugador
                idx = self.io.elegir_almacen_carta(jugador, cartas_mesa)
                carta = cartas_mesa.pop(idx)
                jugador.recibeCarta(carta)
                print(f"{jugador.nombre} elige {carta.nombre}.")
        finally:
            if hasattr(self.io, 'current_jugador'):
                self.io.current_jugador = jugador_anterior

    def diligencia(self, id_jugador, id_carta):
        """Juega la Diligencia: el jugador roba 2 cartas del mazo."""
        self.perder_carta(id_jugador, id_carta)
        self.recibe_carta(id_jugador)
        self.recibe_carta(id_jugador)

    def wells_fargo(self, id_jugador, id_carta):
        """Juega Wells Fargo: el jugador roba 3 cartas del mazo."""
        self.perder_carta(id_jugador, id_carta)
        self.recibe_carta(id_jugador)
        self.recibe_carta(id_jugador)
        self.recibe_carta(id_jugador)

    def panico(self, id_jugador, id_enemigo, id_carta, id_carta_rival):
        """Juega el Pánico: roba una carta (de mano o equipada) de un rival en alcance (distancia ≤1)."""
        if id_enemigo is None:
            print("No hay ningún rival al alcance")
            return
        rival = self.jugadores[id_enemigo]
        if id_carta_rival is None or (not rival.cartasMano and not rival.cartasEquipadas):
            print("El enemigo no tiene cartas para robar")
            return
        origen, indice = id_carta_rival
        self.perder_carta(id_jugador, id_carta)
        if origen == "mano":
            self.robar_carta_mano(id_enemigo, indice, id_jugador)
        else:
            carta = self.quitar_carta_equipada(id_enemigo, indice)
            self.jugadores[id_jugador].recibeCarta(carta)

    def ingExplosiva(self, id_jugador, id_enemigo, id_carta, id_carta_rival):
        """Juega la Ingeniería Explosiva: descarta una carta de cualquier rival sin límite de distancia."""
        if id_enemigo is None:
            print("No hay ningún rival al alcance")
            return
        rival = self.jugadores[id_enemigo]
        if id_carta_rival is None or (not rival.cartasMano and not rival.cartasEquipadas):
            print("El enemigo no tiene cartas para descartar")
            return
        origen, indice = id_carta_rival
        self.perder_carta(id_jugador, id_carta)
        if origen == "mano":
            self.perder_carta(id_enemigo, indice)
        else:
            carta = self.quitar_carta_equipada(id_enemigo, indice)
            self._discard_card(carta)
    
    def usar_carta(self, id_jugador, id_carta):
        carta = self.jugadores[id_jugador].getCarta(id_carta)
        clase = carta.idClase
        if clase in {1, 2, 3, 4, 5}:
            self.anadir_arma(id_jugador, id_carta)
            return
        if clase == 6:
            id_enemigo = self.elegir_rival(id_jugador)
            self.poner_carcel(id_jugador, id_enemigo, id_carta)
            return
        if clase == 7:
            self.mustang(id_jugador, id_carta)
            return
        if clase == 8:
            self.barril(id_jugador, id_carta)
            return
        if clase == 9:
            self.poner_dinamita(id_jugador, id_carta)
            return
        if clase == 10:
            self.mira_telescopica(id_jugador, id_carta)
            return
        if clase == 11:
            id_enemigo = self.elegir_rival(id_jugador, requiere_alcance=True)
            self.bang(id_jugador, id_enemigo, id_carta)
            return
        if clase == 12:
            if self.jugadores[id_jugador].personaje.nombre == "Calamity Janet":
                id_enemigo = self.elegir_rival(id_jugador, requiere_alcance=True)
                self.bang(id_jugador, id_enemigo, id_carta)
            else:
                print("No puedes usar un FALLASTE directamente, solo como respuesta a un BANG")
            return
        if clase == 13:
            self.cerveza(id_jugador, id_carta)
            return
        if clase == 14:
            self.indios(id_jugador, id_carta)
            return
        if clase == 15:
            id_enemigo = self.elegir_rival(id_jugador, requiere_alcance=False)
            self.duelo(id_jugador, id_enemigo, id_carta)
            return
        if clase == 16:
            self.ametralladora(id_jugador, id_carta)
            return
        if clase == 17:
            id_enemigo = self.elegir_rival(id_jugador, requiere_alcance=True)
            id_carta_rival = self.elegir_carta_rival(id_jugador, id_enemigo) if id_enemigo is not None else None
            self.panico(id_jugador, id_enemigo, id_carta, id_carta_rival)
            return
        if clase == 18:
            id_enemigo = self.elegir_rival(id_jugador, requiere_alcance=False)
            id_carta_rival = self.elegir_carta_rival(id_jugador, id_enemigo) if id_enemigo is not None else None
            self.ingExplosiva(id_jugador, id_enemigo, id_carta, id_carta_rival)
            return
        if clase == 19:
            self.saloon(id_jugador, id_carta)
            return
        if clase == 20:
            self.almacen(id_jugador, id_carta)
            return
        if clase == 21:
            self.diligencia(id_jugador, id_carta)
            return
        if clase == 22:
            self.wells_fargo(id_jugador, id_carta)
            return
        print(f"Carta con clase {clase} aún no está implementada")

    def _desenfundar(self, id_jugador):
        """Roba una carta para un chequeo de barril/cárcel/dinamita.
        Lucky Duke roba 2 y elige cuál usar; ambas se descartan.
        Devuelve la carta elegida (ya descartada) para comprobar palo/numero.
        """
        jugador = self.jugadores[id_jugador]
        if jugador.personaje.nombre == "Lucky Duke":
            carta1 = self._draw_from_deck()
            carta2 = self._draw_from_deck()
            elegida = self.io.elegir_lucky_duke(jugador, carta1, carta2)
            self._discard_card(carta1)
            self._discard_card(carta2)
            return elegida
        carta = self._draw_from_deck()
        self._discard_card(carta)
        return carta

    def _fase_robo(self, id_jugador):
        """Ejecuta la fase de robo del turno según el personaje del jugador.

        La mayoría roba 2 cartas del mazo. Excepciones:
        - Black Jack: muestra la 2ª carta; si es ♥/♦ roba una extra.
        - Jesse Jones: puede robar la 1ª carta de la mano de un rival.
        - Kit Carlson: ve 3 cartas, elige 2 y devuelve 1 al mazo.
        - Pedro Ramírez: puede coger la carta superior del descarte en lugar de robar.
        """
        jugador = self.jugadores[id_jugador]
        nombre = jugador.personaje.nombre

        if nombre == "Black Jack":
            self.recibe_carta(id_jugador)
            carta2 = self._draw_from_deck()
            jugador.recibeCarta(carta2)
            print(f"Black Jack muestra su 2ª carta: {carta2.nombre} ({carta2.palo} {carta2.numero})")
            if carta2.palo in {"Corazones", "Diamantes"}:
                print(f"¡Es de {carta2.palo}! Black Jack roba una carta extra.")
                self.recibe_carta(id_jugador)

        elif nombre == "Jesse Jones":
            rivales = [j for j in self.jugadores if j.idJugador != id_jugador and not j.muerto and j.cartasMano]
            id_rival = self.io.elegir_robo_jesse(jugador, rivales)
            if id_rival is not None:
                rival = self.jugadores[id_rival]
                indice = random.randint(0, len(rival.cartasMano) - 1)
                carta = rival.cartasMano[indice]
                rival.pierdeCarta(indice)
                jugador.recibeCarta(carta)
                print(f"Jesse Jones roba una carta al azar de {rival.nombre}.")
            else:
                self.recibe_carta(id_jugador)
            self.recibe_carta(id_jugador)

        elif nombre == "Kit Carlson":
            cartas = [self._draw_from_deck() for _ in range(3)]
            idx_devolver = self.io.elegir_kit_carlson(jugador, cartas)
            carta_devolver = cartas.pop(idx_devolver)
            self.baraja.append(carta_devolver)
            for carta in cartas:
                jugador.recibeCarta(carta)
            print(f"Kit Carlson devuelve {carta_devolver.nombre} al mazo.")

        elif nombre == "Pedro Ramirez":
            if self.monton_descartes:
                carta_top = self.monton_descartes[-1]
                coger_descarte = self.io.elegir_robo_pedro(jugador, carta_top)
                if coger_descarte:
                    jugador.recibeCarta(self.monton_descartes.pop())
                    print(f"Pedro Ramírez coge {jugador.cartasMano[-1].nombre} del descarte.")
                else:
                    self.recibe_carta(id_jugador)
            else:
                self.recibe_carta(id_jugador)
            self.recibe_carta(id_jugador)

        else:
            self.recibe_carta(id_jugador)
            self.recibe_carta(id_jugador)

    def turno_jugador(self, id_jugador):
        """Ejecuta el turno completo de un jugador: dinamita, cárcel, robo y fase de juego.

        Orden:
        1. Chequeo de Dinamita (explota en ♠2-9 infligiendo 3 daños; si no, pasa al siguiente).
        2. Chequeo de Cárcel (pierde el turno si no saca ♥).
        3. Fase de robo (_fase_robo).
        4. Bucle de juego: el jugador usa cartas hasta declarar fin de turno.
        5. Descarte hasta quedar con cartas ≤ vidas actuales.
        """
        if self.game_over:
            return
        jugador = self.jugadores[id_jugador]
        if jugador.muerto:
            return
        if jugador.dinamita:
            carta_reveal = self._desenfundar(id_jugador)
            indice_din = next(i for i, c in enumerate(jugador.cartasEquipadas) if c.idClase == 9)
            dinamita_carta = self.quitar_carta_equipada(id_jugador, indice_din)
            if carta_reveal.palo == "Picas" and carta_reveal.numero in range(2, 10):
                print(f"\n{jugador.nombre} ha sacado {carta_reveal.nombre} ({carta_reveal.palo} {carta_reveal.numero}) y la dinamita explota.\n")
                self._discard_card(dinamita_carta)
                self.infligir_dano(id_jugador, cantidad=3)
            else:
                print(f"\n{jugador.nombre} ha sacado {carta_reveal.nombre} ({carta_reveal.palo} {carta_reveal.numero}) y la dinamita no explota.\n")
                n = len(self.jugadores)
                next_id = (id_jugador + 1) % n
                while self.jugadores[next_id].muerto and next_id != id_jugador:
                    next_id = (next_id + 1) % n
                next_jugador = self.jugadores[next_id]
                if not next_jugador.muerto:
                    next_jugador.ponerDinamita()
                    next_jugador.equipaCarta(dinamita_carta)
                    print(f"{next_jugador.nombre} recibe la dinamita y la equipa.\n")
                else:
                    self._discard_card(dinamita_carta)
            if self.game_over or jugador.muerto:
                return

        if jugador.carcel:
            carta_reveal = self._desenfundar(id_jugador)
            indice_carcel = next(i for i, c in enumerate(jugador.cartasEquipadas) if c.idClase == 6)
            carcel_carta = self.quitar_carta_equipada(id_jugador, indice_carcel)
            self._discard_card(carcel_carta)
            if carta_reveal.palo == "Corazones":
                print(f"\n{jugador.nombre} ha sacado {carta_reveal.nombre} de Corazones y sale de la cárcel.\n")
            else:
                print(f"\n{jugador.nombre} está en la cárcel y pierde su turno.\n")
                return
        jugador.contBang = 0
        print(f"--- Turno de {jugador.nombre} ({jugador.personaje.nombre}) ---")
        self._fase_robo(id_jugador)

        while True:
            opciones = [str(i + 1) for i in range(len(jugador.cartasMano))]

            permitir_poder = self.poder_disponible(id_jugador)
            eleccion = self.io.elegir_carta(
                jugador, "¿Quieres usar una carta? Haz clic sobre ella o pulsa Fin de turno.",
                opciones, permitir_fin=True, permitir_poder=permitir_poder,
            ).strip().upper()
            if eleccion == "PODER":
                self.usar_poder(id_jugador)
                continue
            if eleccion == "FIN":
                while len(jugador.cartasMano) > jugador.vidas:
                    options_desc = [str(i + 1) for i in range(len(jugador.cartasMano))]
                    descartar = self.io.elegir_carta(
                        jugador, "Tienes que descartar una carta. Haz clic sobre ella.",
                        options_desc, permitir_fin=False,
                    ).strip()
                    if descartar.isdigit():
                        indice = int(descartar) - 1
                        if 0 <= indice < len(jugador.cartasMano):
                            self.perder_carta(id_jugador, indice)
                            continue
                    print("Escribe un número válido")
                print("Has terminado tu turno")
                break

            if not eleccion.isdigit():
                print("Escribe un número válido o FIN")
                continue

            indice = int(eleccion) - 1
            if 0 <= indice < len(jugador.cartasMano):
                self.usar_carta(id_jugador, indice)
                continue
            print("Escribe un índice de carta válido")

    def partida(self):
        """Bucle principal de la partida: reparte turnos en orden circular hasta que game_over sea True.

        El turno siempre empieza por el Sheriff. Al terminar llama a io.mostrar_game_over si está disponible.
        """
        sheriff = next((j for j in self.jugadores if j.rol == "Sheriff"), self.jugadores[0])
        self.turno = sheriff.idJugador
        while not self.game_over:
            self.turno %= len(self.jugadores)
            if self.turno == sheriff.idJugador:
                self.ronda += 1
            jugador = self.jugadores[self.turno]
            self.turno += 1
            if jugador.muerto:
                continue
            self.turno_jugador(jugador.idJugador)
        if hasattr(self.io, 'mostrar_game_over'):
            self.io.mostrar_game_over(self.ganador)


def build_player_names(num_players, io=None):
    """Solicita un nombre por cada jugador y devuelve la lista.

    Args:
        num_players (int): Número de jugadores.
        io: Adaptador IO con método prompt(). Si es None se usa ConsoleIO.

    Returns:
        list[str]: Nombres introducidos (usa "JugadorN" si el campo queda vacío).
    """
    io = io or ConsoleIO()
    nombres = []
    for i in range(num_players):
        nombre = io.prompt(f"Jugador {i+1}: ").strip()
        nombres.append(nombre or f"Jugador{i+1}")
    return nombres
