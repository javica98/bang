class Personaje:
    """Representa un personaje del juego con su nombre y puntos de vida base.

    Attributes:
        idPersonaje (int): Identificador único del personaje.
        nombre (str): Nombre del personaje (e.g. "Willy the Kid").
        vidas (int): Puntos de vida base del personaje (sin bonificación de Sheriff).
    """

    def __init__(self, idPersonaje, nombre, vidas):
        self.idPersonaje = idPersonaje
        self.nombre = nombre
        self.vidas = vidas

    def __str__(self):
        return (
            "-----------------\n"
            f"-IdPersonaje: {self.idPersonaje}\n"
            f"-Nombre: {self.nombre}\n"
            f"-Vidas: {self.vidas}\n"
            "-----------------"
        )


class Carta:
    """Representa una carta física del mazo.

    Cada carta tiene una clase (idClase) que determina su efecto en el juego,
    y un identificador único de instancia (idObjeto) para distinguir cartas
    del mismo tipo. El palo y número se asignan aleatoriamente al crear el mazo.

    Clases de carta (idClase):
        1  - Volcanic       (arma, rango 1, Bang ilimitados)
        2  - Schofield      (arma, rango 2)
        3  - Remington      (arma, rango 3)
        4  - Carabina       (arma, rango 4)
        5  - Winchester     (arma, rango 5)
        6  - Cárcel         (objeto equipable en rival, pierde turno si saca ♠)
        7  - Mustang        (objeto propio, +1 distancia para rivales)
        8  - Barril         (objeto propio, intento de esquivar Bang con ♥)
        9  - Dinamita       (objeto propio, explota en ♠2-9 infligiendo 3 daños)
        10 - Mira Telescópica (objeto propio, -1 distancia al atacar)
        11 - Bang           (efecto: 1 daño al objetivo si no esquiva)
        12 - Fallaste       (respuesta a Bang para esquivar)
        13 - Cerveza        (recupera 1 vida; inútil si quedan ≤2 jugadores)
        14 - Indios         (todos los rivales usan Bang o pierden 1 vida)
        15 - Duelo          (intercambio de Bangs hasta que uno no pueda)
        16 - Ametralladora  (todos los rivales usan Fallaste o pierden 1 vida)
        17 - Pánico         (roba una carta al azar de un rival en alcance)
        18 - Ing. Explosiva (roba una carta al azar de cualquier rival)
        19 - Saloon         (todos los jugadores vivos recuperan 1 vida)
        20 - Almacén        (reparte N cartas boca arriba; cada jugador elige 1)
        21 - Diligencia     (roba 2 cartas del mazo)
        22 - Wells Fargo    (roba 3 cartas del mazo)

    Attributes:
        idObjeto (int): Identificador único de esta instancia de carta.
        idClase (int): Tipo de carta según la tabla anterior.
        nombre (str): Nombre de la carta (e.g. "Bang", "Cárcel").
        tipo (str): Categoría de la carta ("Efecto", "Arma", "Objeto").
        numero (int | None): Número de baraja asignado aleatoriamente (1-13).
        palo (str | None): Palo asignado aleatoriamente ("Corazones", "Diamantes",
            "Picas", "Treboles").
    """

    def __init__(self, idObjeto, idClase, nombre, tipo):
        self.idObjeto = idObjeto
        self.idClase = idClase
        self.nombre = nombre
        self.tipo = tipo
        self.numero = None
        self.palo = None

    def __str__(self):
        return (
            "-----------------\n"
            f"-IdObjeto: {self.idObjeto}\n"
            f"-IdClase: {self.idClase}\n"
            f"-Nombre: {self.nombre}\n"
            f"-Tipo: {self.tipo}\n"
            "-----------------"
        )


class Jugador:
    """Representa a un jugador durante la partida.

    Gestiona el estado completo del jugador: vidas, mano de cartas,
    cartas equipadas y todos los modificadores de estado (barril, mustang, etc.).

    El Sheriff recibe +1 vida máxima respecto a las vidas base de su personaje.

    Attributes:
        idJugador (int): Índice del jugador en la lista de la partida (0-based).
        nombre (str): Nombre introducido por el usuario.
        rol (str): Rol secreto asignado ("Sheriff", "Ayudante", "Forajido", "Renegado").
        personaje (Personaje): Personaje elegido con su habilidad especial.
        vidas (int): Vidas actuales.
        vidasMax (int): Vidas máximas (vidas del personaje +1 si es Sheriff).
        cartasMano (list[Carta]): Cartas en la mano del jugador.
        cartasEquipadas (list[Carta]): Cartas en juego (armas y objetos equipados).
        arma (int): idClase del arma equipada (0 = Colt por defecto, rango 1).
        distancia (int): Distancia de ataque actual (modificada por el arma).
        carcel (bool): True si tiene una Cárcel equipada (pierde el próximo turno si falla el chequeo).
        mustang (bool): True si tiene un Mustang equipado (+1 distancia para rivales que le atacan).
        barril (bool): True si tiene un Barril equipado (intento de esquivar Bang automáticamente).
        dinamita (bool): True si tiene una Dinamita equipada (explota en ♠2-9).
        miraTelescopica (bool): True si tiene Mira Telescópica (-1 distancia al atacar).
        volcanic (bool): True si tiene la Volcanic equipada (Bang ilimitados por turno).
        muerto (bool): True si el jugador ha sido eliminado.
        contBang (int): Número de Bang jugados en el turno actual (límite 1 salvo Volcanic/Willy).
    """

    def __init__(self, idJugador, nombre, personaje, rol, cartasMano=None):
        self.idJugador = idJugador
        self.nombre = nombre
        self.rol = rol
        self.personaje = personaje
        if rol == "Sheriff":
            self.vidasMax = personaje.vidas + 1
            self.vidas = personaje.vidas + 1
        else:
            self.vidasMax = personaje.vidas
            self.vidas = personaje.vidas
        self.cartasMano = cartasMano or []
        self.cartasEquipadas = []
        self.arma = 0
        self.distancia = 1
        self.carcel = False
        self.mustang = False
        self.barril = False
        self.dinamita = False
        self.miraTelescopica = False
        self.volcanic = False
        self.muerto = False
        self.contBang = 0

    def perderVida(self):
        """Resta 1 vida y marca al jugador como muerto si llega a 0."""
        self.vidas -= 1
        if self.vidas <= 0:
            self.vidas = 0
            self.muerto = True
            print(f"{self.nombre} HA MUERTO")

    def ganarVida(self):
        """Suma 1 vida sin superar vidasMax."""
        if self.vidas < self.vidasMax:
            self.vidas += 1

    def _validar_indice_carta(self, idCarta):
        """Lanza IndexError si idCarta no es un índice válido de cartasMano."""
        if not 0 <= idCarta < len(self.cartasMano):
            raise IndexError(f"Índice de carta fuera de rango: {idCarta}")

    def getCarta(self, idCarta):
        """Devuelve la carta en la posición idCarta sin retirarla de la mano."""
        self._validar_indice_carta(idCarta)
        return self.cartasMano[idCarta]

    def recibeCarta(self, carta):
        """Añade una carta al final de la mano."""
        self.cartasMano.append(carta)

    def pierdeCarta(self, idCarta):
        """Retira la carta en la posición idCarta de la mano."""
        self._validar_indice_carta(idCarta)
        self.cartasMano.pop(idCarta)

    def equipaCarta(self, carta):
        """Añade una carta a la zona de cartas equipadas (en juego)."""
        self.cartasEquipadas.append(carta)

    def pierdeCartaEquipada(self, idCarta):
        """Retira y devuelve la carta equipada en la posición idCarta."""
        return self.cartasEquipadas.pop(idCarta)

    def cambioArma(self, arma, distancia):
        """Actualiza el arma equipada y el rango de ataque resultante.

        Args:
            arma (int): idClase del arma nueva (0 = Colt por defecto).
            distancia (int): Nuevo rango de ataque.
        """
        self.arma = arma
        self.distancia = distancia

    def _set_estado(self, nombre_estado, valor):
        """Setter genérico para los flags de estado booleanos."""
        setattr(self, nombre_estado, valor)

    def ponerCarcel(self):
        """Activa el estado 'en cárcel' (pierde turno si falla el chequeo de ♥)."""
        self._set_estado("carcel", True)

    def quitarCarcel(self):
        """Desactiva el estado 'en cárcel'."""
        self._set_estado("carcel", False)

    def ponerMustang(self):
        """Equipa Mustang: los rivales ven la distancia a este jugador aumentada en 1."""
        self._set_estado("mustang", True)

    def quitarMustang(self):
        """Retira el Mustang."""
        self._set_estado("mustang", False)

    def ponerBarril(self):
        """Equipa Barril: al recibir un Bang, intenta esquivar automáticamente con ♥."""
        self._set_estado("barril", True)

    def quitarBarril(self):
        """Retira el Barril."""
        self._set_estado("barril", False)

    def ponerDinamita(self):
        """Equipa Dinamita: al inicio del turno comprueba si explota (♠2-9 = 3 daños)."""
        self._set_estado("dinamita", True)

    def quitarDinamita(self):
        """Retira la Dinamita."""
        self._set_estado("dinamita", False)

    def ponerMiraTelescopica(self):
        """Equipa Mira Telescópica: reduce en 1 la distancia al atacar."""
        self._set_estado("miraTelescopica", True)

    def quitarMiraTelescopica(self):
        """Retira la Mira Telescópica."""
        self._set_estado("miraTelescopica", False)

    def ponerVolcanic(self):
        """Equipa la Volcanic: permite usar Bang ilimitados y fija el rango a 1."""
        self._set_estado("volcanic", True)
        self.distancia = 1

    def quitarVolcanic(self):
        """Retira la Volcanic."""
        self._set_estado("volcanic", False)

    @property
    def nombre_personaje(self):
        """Nombre del personaje elegido por el jugador."""
        return self.personaje.nombre

    def __str__(self):
        cartas_str = "\n".join(str(carta) for carta in self.cartasMano)
        return (
            "-----------------\n"
            f"-IdJugador: {self.idJugador}\n"
            f"-Nombre: {self.nombre}\n"
            f"-Rol: {self.rol}\n"
            f"-Personaje: {self.personaje.nombre}\n"
            f"-Vidas: {self.vidas}/{self.vidasMax}\n"
            "-----------------\n"
            "CARTAS EN MANO:\n"
            f"{cartas_str}\n"
        )
