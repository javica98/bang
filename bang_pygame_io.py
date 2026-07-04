import sys
import math
import builtins
import pygame
import textwrap

from bang_game import ConsoleIO, DESCRIPCIONES_PERSONAJE


ARMA_NOMBRES = {
    0: "Colt .45",
    1: "Volcanic",
    2: "Schofield",
    3: "Remington",
    4: "Carabina",
    5: "Winchester",
}

# (atributo en Jugador, etiqueta a mostrar en la cartita azul)
ESTADOS_BADGES = [
    ("carcel", "CARC"),
    ("mustang", "MUST"),
    ("barril", "BARR"),
    ("dinamita", "DINA"),
    ("miraTelescopica", "MIRA"),
    ("volcanic", "VOLC"),
]


LOG_W = 260

class PygameIO:
    def __init__(self, size=(1280, 640), font_size=20):
        pygame.init()
        pygame.font.init()
        self.size = size
        self.screen = pygame.display.set_mode(self.size)
        pygame.display.set_caption("BANG!")
        self.font = pygame.font.SysFont('arial', font_size)
        self.small_font = pygame.font.SysFont('arial', 14)
        self.bold_font = pygame.font.SysFont('arial', 18, bold=True)
        self.log_font = pygame.font.SysFont('arial', 12)
        self.clock = pygame.time.Clock()

        self.juego = None
        self.current_jugador = None
        self.log_messages = []

        game_w = self.size[0] - LOG_W
        self.board_rect = pygame.Rect(0, 0, game_w, 430)
        self.hand_rect = pygame.Rect(0, 430, game_w, 135)
        self.prompt_rect = pygame.Rect(0, 565, game_w, self.size[1] - 565)
        self.log_rect = pygame.Rect(game_w, 0, LOG_W, self.size[1])

        # Captura prints del juego para mostrarlos en el chat
        _self = self
        _orig_print = builtins.print
        def _patched_print(*args, **kwargs):
            _orig_print(*args, **kwargs)
            msg = " ".join(str(a) for a in args)
            for line in msg.splitlines():
                line = line.strip()
                if line:
                    _self.log_messages.append(line)
            if len(_self.log_messages) > 200:
                _self.log_messages = _self.log_messages[-200:]
        builtins.print = _patched_print

    def set_game(self, juego):
        """Guarda una referencia a la partida para poder dibujar el tablero."""
        self.juego = juego

    def _render_text(self, text, top=10, padding=10, font=None, width=95):
        font = font or self.font
        lines = textwrap.wrap(text, width=width)
        y = top
        for line in lines:
            surf = font.render(line, True, (0, 0, 0))
            self.screen.blit(surf, (padding, y))
            y += surf.get_height() + 4
        return y

    def _draw_log(self):
        """Dibuja el panel de chat/log en el lateral derecho."""
        pygame.draw.rect(self.screen, (30, 30, 30), self.log_rect)
        pygame.draw.rect(self.screen, (100, 100, 100), self.log_rect, 2)
        titulo = self.bold_font.render("LOG", True, (220, 220, 100))
        self.screen.blit(titulo, (self.log_rect.x + 8, 6))
        line_h = self.log_font.get_height() + 2
        visible = (self.log_rect.height - 30) // line_h
        msgs = self.log_messages[-visible:]
        y = self.log_rect.y + 28
        for msg in msgs:
            wrapped = textwrap.wrap(msg, width=30)
            for line in wrapped:
                surf = self.log_font.render(line, True, (200, 200, 200))
                self.screen.blit(surf, (self.log_rect.x + 6, y))
                y += line_h
        pygame.draw.line(self.screen, (100, 100, 100),
                         (self.log_rect.x, 0), (self.log_rect.x, self.size[1]), 2)

    def _draw_board(self):
        """Dibuja el tablero con los paneles de cada jugador y devuelve un diccionario
        {idJugador: rect} para poder detectar clics sobre el panel de un jugador.
        """
        pygame.draw.rect(self.screen, (222, 184, 135), self.board_rect)
        self._draw_log()

        if self.juego is None:
            return {}

        jugadores = self.juego.jugadores
        n = len(jugadores)
        if n == 0:
            return {}

        turno_actual = (self.juego.turno - 1) % n
        self._render_text(
            f"Ronda {self.juego.ronda}  -  Turno de: {jugadores[turno_actual].nombre}",
            top=10, font=self.bold_font,
        )

        cx, cy = self.board_rect.centerx, self.board_rect.centery + 15
        radius_x = 380
        radius_y = 100
        panel_w, panel_h = 200, 140

        panel_rects = {}
        for jugador in jugadores:
            angle = -math.pi / 2 + 2 * math.pi * jugador.idJugador / n
            x = cx + radius_x * math.cos(angle) - panel_w // 2
            y = cy + radius_y * math.sin(angle) - panel_h // 2
            rect = pygame.Rect(int(x), int(y), panel_w, panel_h)

            es_turno = turno_actual == jugador.idJugador
            if jugador.muerto:
                fill, border = (120, 120, 120), (60, 60, 60)
            elif es_turno:
                fill, border = (255, 250, 205), (200, 150, 0)
            else:
                fill, border = (255, 255, 255), (0, 0, 0)

            pygame.draw.rect(self.screen, fill, rect)
            pygame.draw.rect(self.screen, border, rect, 3 if es_turno else 2)

            ty = rect.y + 6
            nombre_surf = self.bold_font.render(jugador.nombre, True, (0, 0, 0))
            self.screen.blit(nombre_surf, (rect.x + 8, ty))
            if jugador.rol == "Sheriff":
                estrella_cx = rect.x + 12 + nombre_surf.get_width() + 10
                estrella_cy = ty + nombre_surf.get_height() // 2
                pygame.draw.circle(self.screen, (255, 215, 0), (estrella_cx, estrella_cy), 7)
                pygame.draw.circle(self.screen, (0, 0, 0), (estrella_cx, estrella_cy), 7, 1)
            ty += nombre_surf.get_height() + 2

            personaje_surf = self.small_font.render(jugador.nombre_personaje, True, (60, 60, 60))
            self.screen.blit(personaje_surf, (rect.x + 8, ty))
            ty += personaje_surf.get_height() + 4

            # Vidas como circulos (rojo = vida actual, blanco = vida perdida)
            for i in range(jugador.vidasMax):
                color = (200, 0, 0) if i < jugador.vidas else (255, 255, 255)
                cx_life = rect.x + 12 + i * 16
                pygame.draw.circle(self.screen, color, (cx_life, ty + 6), 6)
                pygame.draw.circle(self.screen, (0, 0, 0), (cx_life, ty + 6), 6, 1)
            ty += 20

            # El rol solo se revela al morir (el Sheriff ya se marca con la estrella)
            if jugador.muerto and jugador.rol != "Sheriff":
                rol_surf = self.small_font.render(f"Rol: {jugador.rol}", True, (0, 0, 100))
                self.screen.blit(rol_surf, (rect.x + 8, ty))
                ty += rol_surf.get_height() + 2

            arma_nombre = ARMA_NOMBRES.get(jugador.arma, str(jugador.arma))
            arma_surf = self.small_font.render(f"{arma_nombre} (alcance {jugador.distancia})", True, (0, 0, 0))
            self.screen.blit(arma_surf, (rect.x + 8, ty))
            ty += arma_surf.get_height() + 2

            self._draw_estado_cards(rect, jugador)
            self._draw_mano_oculta(rect, jugador)

            panel_rects[jugador.idJugador] = rect

        return panel_rects

    def _draw_estado_cards(self, rect, jugador):
        """Dibuja las cartas de estado activas (carcel, mustang, barril, etc.)
        como pequeñas cartas azules apiladas en el borde derecho del panel.
        """
        card_w, card_h = 38, 18
        spacing = 2
        estado_font = pygame.font.SysFont('arial', 11, bold=True)

        estados_activos = [label for attr, label in ESTADOS_BADGES if getattr(jugador, attr, False)]
        x = rect.right - card_w - 4
        y = rect.y + 56
        for label in estados_activos:
            card_rect = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (50, 90, 200), card_rect)
            pygame.draw.rect(self.screen, (20, 40, 120), card_rect, 1)

            texto_surf = estado_font.render(label, True, (255, 255, 255))
            texto_rect = texto_surf.get_rect(center=card_rect.center)
            self.screen.blit(texto_surf, texto_rect)

            y += card_h + spacing

    def _draw_mano_oculta(self, rect, jugador):
        """Dibuja las cartas de la mano del jugador como cartas boca abajo,
        una por una, en la parte inferior de su panel.
        """
        card_w, card_h = 16, 22
        spacing = 2

        x = rect.x + 6
        y = rect.bottom - card_h - 4
        for _ in jugador.cartasMano:
            if x + card_w > rect.right - 6:
                break
            card_rect = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (150, 30, 30), card_rect)
            pygame.draw.rect(self.screen, (60, 10, 10), card_rect, 1)
            x += card_w + spacing

    def _draw_hand(self):
        """Dibuja la mano del jugador actual y devuelve una lista de (rect, indice)
        para cada carta dibujada, de modo que se puedan detectar clics sobre ellas.
        """
        pygame.draw.rect(self.screen, (200, 200, 200), self.hand_rect)
        if self.current_jugador is None:
            return []

        jugador = self.current_jugador
        titulo = f"Mano de {jugador.nombre} ({jugador.vidas}/{jugador.vidasMax} vidas):"
        self._render_text(titulo, top=self.hand_rect.y + 5, font=self.bold_font)

        card_w, card_h = 80, 95
        spacing = 10
        start_x = 10
        y = self.hand_rect.y + 35

        rects = []
        for i, carta in enumerate(jugador.cartasMano):
            x = start_x + i * (card_w + spacing)
            if x + card_w > self.size[0]:
                break
            rect = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (255, 255, 255), rect)
            borde = (30, 80, 200) if carta.tipo in ("Objeto", "Arma") else (0, 0, 0)
            pygame.draw.rect(self.screen, borde, rect, 2)

            num_surf = self.small_font.render(str(i + 1), True, (100, 100, 100))
            self.screen.blit(num_surf, (rect.x + 4, rect.y + 4))

            nombre = getattr(carta, 'nombre', '')
            for j, line in enumerate(textwrap.wrap(nombre, width=12)):
                line_surf = self.small_font.render(line, True, (0, 0, 0))
                self.screen.blit(line_surf, (rect.x + 4, rect.y + 22 + j * 16))

            tipo_surf = self.small_font.render(carta.tipo, True, (100, 100, 100))
            self.screen.blit(tipo_surf, (rect.x + 4, rect.bottom - 18))

            rects.append((rect, i))

        return rects

    def _draw_hand_oculta(self, jugador):
        """Dibuja la mano de otro jugador boca abajo (para robarle una carta) seguida
        de sus cartas equipadas boca arriba, y devuelve una lista de
        (rect, ("mano"|"equipo", indice)) para detectar clics.
        """
        pygame.draw.rect(self.screen, (200, 200, 200), self.hand_rect)

        titulo = f"Cartas de {jugador.nombre} (elige una para robar):"
        self._render_text(titulo, top=self.hand_rect.y + 5, font=self.bold_font)

        card_w, card_h = 80, 95
        spacing = 10
        start_x = 10
        y = self.hand_rect.y + 35

        rects = []
        i = 0
        for _ in jugador.cartasMano:
            x = start_x + i * (card_w + spacing)
            if x + card_w > self.size[0]:
                break
            rect = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (150, 30, 30), rect)
            pygame.draw.rect(self.screen, (60, 10, 10), rect, 2)
            rects.append((rect, ("mano", len(rects))))
            i += 1

        for indice_equipo, carta in enumerate(jugador.cartasEquipadas):
            x = start_x + i * (card_w + spacing)
            if x + card_w > self.size[0]:
                break
            rect = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (255, 255, 255), rect)
            pygame.draw.rect(self.screen, (30, 80, 200), rect, 2)
            for j, line in enumerate(textwrap.wrap(carta.nombre, width=12)):
                line_surf = self.small_font.render(line, True, (0, 0, 0))
                self.screen.blit(line_surf, (rect.x + 4, rect.y + 4 + j * 16))
            equipada_surf = self.small_font.render("(equipada)", True, (100, 100, 100))
            self.screen.blit(equipada_surf, (rect.x + 4, rect.bottom - 18))
            rects.append((rect, ("equipo", indice_equipo)))
            i += 1

        return rects

    def elegir_carta_rival(self, rival, text):
        """Permite elegir una carta de `rival` (de su mano boca abajo, o equipada
        boca arriba) haciendo clic.
        :return: tupla (origen, indice), donde origen es "mano" o "equipo".
        """
        while True:
            self._draw_board()
            card_rects = self._draw_hand_oculta(rival)
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text(text, top=self.prompt_rect.y + 5, width=100)

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    for rect, valor in card_rects:
                        if rect.collidepoint(pos):
                            return valor
            self.clock.tick(30)

    def _draw_almacen(self, cartas):
        """Dibuja las cartas del Almacén boca arriba en el área de mano y devuelve
        una lista de (rect, indice) para detectar clics.
        """
        pygame.draw.rect(self.screen, (200, 200, 200), self.hand_rect)
        self._render_text("Almacén — elige una carta:", top=self.hand_rect.y + 5, font=self.bold_font)

        card_w, card_h = 80, 95
        spacing = 10
        start_x = 10
        y = self.hand_rect.y + 35

        rects = []
        for i, carta in enumerate(cartas):
            x = start_x + i * (card_w + spacing)
            if x + card_w > self.size[0]:
                break
            rect = pygame.Rect(x, y, card_w, card_h)
            pygame.draw.rect(self.screen, (255, 255, 255), rect)
            pygame.draw.rect(self.screen, (180, 120, 0), rect, 2)
            for j, line in enumerate(textwrap.wrap(carta.nombre, width=12)):
                surf = self.small_font.render(line, True, (0, 0, 0))
                self.screen.blit(surf, (rect.x + 4, rect.y + 4 + j * 16))
            palo_surf = self.small_font.render(f"{carta.palo[:3]} {carta.numero}", True, (100, 60, 0))
            self.screen.blit(palo_surf, (rect.x + 4, rect.bottom - 18))
            rects.append((rect, i))
        return rects

    def elegir_lucky_duke(self, jugador, carta1, carta2):
        """Lucky Duke ve 2 cartas boca arriba y elige cuál usar para el chequeo."""
        cartas = [carta1, carta2]
        card_w, card_h = 80, 95
        spacing = 20
        total_w = 2 * card_w + spacing
        start_x = self.size[0] // 2 - total_w // 2
        y = self.hand_rect.y + 35
        rects = []
        while True:
            self._draw_board()
            pygame.draw.rect(self.screen, (200, 200, 200), self.hand_rect)
            self._render_text(
                f"{jugador.nombre} (Lucky Duke): elige el resultado del desenfunde.",
                top=self.hand_rect.y + 5, font=self.bold_font,
            )
            rects = []
            for i, carta in enumerate(cartas):
                x = start_x + i * (card_w + spacing)
                rect = pygame.Rect(x, y, card_w, card_h)
                pygame.draw.rect(self.screen, (255, 255, 255), rect)
                pygame.draw.rect(self.screen, (180, 120, 0), rect, 2)
                for j, line in enumerate(textwrap.wrap(carta.nombre, width=12)):
                    surf = self.small_font.render(line, True, (0, 0, 0))
                    self.screen.blit(surf, (rect.x + 4, rect.y + 4 + j * 16))
                palo_surf = self.small_font.render(f"{carta.palo[:3]} {carta.numero}", True, (100, 60, 0))
                self.screen.blit(palo_surf, (rect.x + 4, rect.bottom - 18))
                rects.append((rect, i))
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text("Haz clic en la carta que quieres usar.", top=self.prompt_rect.y + 5)
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    for rect, i in rects:
                        if rect.collidepoint(pos):
                            return cartas[i]
            self.clock.tick(30)

    def elegir_robo_jesse(self, jugador, rivales):
        """Jesse Jones elige robar de un rival (clic en panel) o del mazo (botón)."""
        if not rivales:
            return None
        ids_validos = {j.idJugador for j in rivales}
        while True:
            panel_rects, _ = self._render_screen()
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text(
                f"{jugador.nombre} (Jesse Jones): haz clic en un rival para robarle la 1ª carta, o pulsa 'Del mazo'.",
                top=self.prompt_rect.y + 5, width=100,
            )
            for id_j, rect in panel_rects.items():
                if id_j in ids_validos:
                    pygame.draw.rect(self.screen, (0, 180, 0), rect, 4)
            mazo_rect = pygame.Rect(self.size[0] - 170, self.prompt_rect.y + 10, 150, 40)
            self._draw_boton("Del mazo", mazo_rect, (210, 210, 210))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if mazo_rect.collidepoint(pos):
                        return None
                    for id_j, rect in panel_rects.items():
                        if id_j in ids_validos and rect.collidepoint(pos):
                            return id_j
            self.clock.tick(30)

    def elegir_robo_pedro(self, jugador, carta_top):
        """Pedro Ramírez elige coger la carta top del descarte o robar del mazo."""
        card_w, card_h = 80, 95
        card_rect = pygame.Rect(self.size[0] // 2 - card_w // 2, self.hand_rect.y + 20, card_w, card_h)
        while True:
            self._draw_board()
            pygame.draw.rect(self.screen, (200, 200, 200), self.hand_rect)
            self._render_text(
                f"{jugador.nombre} (Pedro Ramírez): carta top del descarte:",
                top=self.hand_rect.y + 5, font=self.bold_font,
            )
            pygame.draw.rect(self.screen, (255, 255, 255), card_rect)
            pygame.draw.rect(self.screen, (180, 120, 0), card_rect, 2)
            for i, line in enumerate(textwrap.wrap(carta_top.nombre, width=12)):
                surf = self.small_font.render(line, True, (0, 0, 0))
                self.screen.blit(surf, (card_rect.x + 4, card_rect.y + 4 + i * 16))
            palo_surf = self.small_font.render(f"{carta_top.palo[:3]} {carta_top.numero}", True, (100, 60, 0))
            self.screen.blit(palo_surf, (card_rect.x + 4, card_rect.bottom - 18))
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text("¿Coges esta carta?", top=self.prompt_rect.y + 5)
            si_rect = pygame.Rect(self.size[0] - 350, self.prompt_rect.y + 10, 150, 40)
            no_rect = pygame.Rect(self.size[0] - 180, self.prompt_rect.y + 10, 150, 40)
            self._draw_boton("Coger descarte", si_rect, (180, 220, 180))
            self._draw_boton("Robar del mazo", no_rect, (210, 210, 210))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if si_rect.collidepoint(pos):
                        return True
                    if no_rect.collidepoint(pos):
                        return False
            self.clock.tick(30)

    def elegir_kit_carlson(self, jugador, cartas):
        """Kit Carlson elige qué carta devolver al mazo de entre las 3 robadas."""
        while True:
            self._draw_board()
            card_rects = self._draw_almacen(cartas)
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text(
                f"{jugador.nombre} (Kit Carlson): haz clic en la carta que quieres devolver al mazo.",
                top=self.prompt_rect.y + 5, width=100,
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    for rect, indice in card_rects:
                        if rect.collidepoint(pos):
                            return indice
            self.clock.tick(30)

    def elegir_almacen_carta(self, jugador, cartas):
        """Muestra las cartas del Almacén boca arriba y espera que `jugador` elija una.
        :return: índice (0-based) de la carta elegida.
        """
        while True:
            self._draw_board()
            card_rects = self._draw_almacen(cartas)
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text(
                f"{jugador.nombre}, elige una carta del Almacén.",
                top=self.prompt_rect.y + 5, width=100,
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    for rect, indice in card_rects:
                        if rect.collidepoint(pos):
                            return indice
            self.clock.tick(30)

    def _render_screen(self):
        panel_rects = self._draw_board()
        card_rects = self._draw_hand()
        return panel_rects, card_rects

    def elegir_personaje(self, nombre_jugador, rol, personaje_a, personaje_b):
        """Muestra los dos personajes disponibles como cartas clicables y
        devuelve el personaje elegido.
        """
        card_w, card_h = 220, 300
        spacing = 60
        total_w = 2 * card_w + spacing
        start_x = (self.size[0] - total_w) // 2
        y = (self.size[1] - card_h) // 2

        while True:
            self.screen.fill((222, 184, 135))
            titulo = f"{nombre_jugador}, eres {rol}. Elige tu personaje:"
            self._render_text(titulo, top=30, font=self.bold_font, width=70)

            rects = []
            for i, personaje in enumerate((personaje_a, personaje_b)):
                x = start_x + i * (card_w + spacing)
                rect = pygame.Rect(x, y, card_w, card_h)
                pygame.draw.rect(self.screen, (255, 255, 255), rect)
                pygame.draw.rect(self.screen, (0, 0, 0), rect, 3)

                ty = rect.y + 20
                for line in textwrap.wrap(personaje.nombre, width=16):
                    line_surf = self.bold_font.render(line, True, (0, 0, 0))
                    self.screen.blit(line_surf, (rect.centerx - line_surf.get_width() // 2, ty))
                    ty += line_surf.get_height() + 4

                ty += 10
                vidas_surf = self.small_font.render(f"Vidas: {personaje.vidas}", True, (0, 0, 0))
                self.screen.blit(vidas_surf, (rect.centerx - vidas_surf.get_width() // 2, ty))
                ty += vidas_surf.get_height() + 8

                for v in range(personaje.vidas):
                    cx_life = rect.centerx - (personaje.vidas * 16) // 2 + 8 + v * 16
                    pygame.draw.circle(self.screen, (200, 0, 0), (cx_life, ty + 6), 6)
                    pygame.draw.circle(self.screen, (0, 0, 0), (cx_life, ty + 6), 6, 1)
                ty += 20

                desc = DESCRIPCIONES_PERSONAJE.get(personaje.nombre, "")
                for line in textwrap.wrap(desc, width=22):
                    desc_surf = self.log_font.render(line, True, (60, 60, 60))
                    self.screen.blit(desc_surf, (rect.x + 10, ty))
                    ty += desc_surf.get_height() + 3

                rects.append((rect, personaje))

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    for rect, personaje in rects:
                        if rect.collidepoint(pos):
                            return personaje
            self.clock.tick(30)

    def prompt(self, text, options=None):
        # sin opciones: pide la entrada por consola (p.ej. nombres de jugadores)
        if not options:
            return ConsoleIO().prompt(text)

        running = True
        while running:
            self._render_screen()
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            y_after_text = self._render_text(text, top=self.prompt_rect.y + 5, width=100)

            btn_w, btn_h, spacing = 130, 36, 10
            total_w = len(options) * btn_w + (len(options) - 1) * spacing
            start_x = max(10, (self.size[0] - total_w) // 2)
            y = max(y_after_text + 10, self.prompt_rect.y + 5)
            if y + btn_h > self.size[1] - 5:
                y = self.size[1] - btn_h - 5

            btns = []
            for i, opt in enumerate(options):
                x = start_x + i * (btn_w + spacing)
                rect = pygame.Rect(x, y, btn_w, btn_h)
                pygame.draw.rect(self.screen, (180, 180, 180), rect)
                pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)
                txt = self.font.render(str(opt), True, (0, 0, 0))
                txt_pos = (x + (btn_w - txt.get_width()) // 2, y + (btn_h - txt.get_height()) // 2)
                self.screen.blit(txt, txt_pos)
                btns.append((rect, str(opt)))

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    for rect, opt in btns:
                        if rect.collidepoint(pos):
                            return opt
            self.clock.tick(30)

    def _draw_boton(self, texto, rect, color_fondo, color_borde=(0, 0, 0)):
        pygame.draw.rect(self.screen, color_fondo, rect)
        pygame.draw.rect(self.screen, color_borde, rect, 2)
        txt = self.bold_font.render(texto, True, (0, 0, 0))
        self.screen.blit(txt, (
            rect.x + (rect.w - txt.get_width()) // 2,
            rect.y + (rect.h - txt.get_height()) // 2,
        ))

    def elegir_carta(self, jugador, text, opciones, permitir_fin=False, permitir_poder=False):
        """Permite elegir una carta de la mano haciendo clic directamente sobre ella.
        :return: string con el índice elegido (p.ej. "1"), "FIN" o "PODER".
        """
        self.current_jugador = jugador
        indices_validos = {int(o) - 1 for o in opciones if o.isdigit()}

        while True:
            _, card_rects = self._render_screen()
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text(text, top=self.prompt_rect.y + 5, width=100)

            for rect, indice in card_rects:
                if indice in indices_validos:
                    pygame.draw.rect(self.screen, (255, 215, 0), rect.inflate(6, 6), 3)

            fin_rect = None
            if permitir_fin:
                fin_rect = pygame.Rect(self.size[0] - 170, self.prompt_rect.y + 10, 150, 40)
                self._draw_boton("Fin de turno", fin_rect, (180, 220, 180))

            poder_rect = None
            if permitir_poder:
                x_poder = (self.size[0] - 170 - 170) if permitir_fin else (self.size[0] - 170)
                poder_rect = pygame.Rect(x_poder, self.prompt_rect.y + 10, 150, 40)
                self._draw_boton("Usar poder", poder_rect, (180, 180, 255))

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if fin_rect and fin_rect.collidepoint(pos):
                        return "FIN"
                    if poder_rect and poder_rect.collidepoint(pos):
                        return "PODER"
                    for rect, indice in card_rects:
                        if indice in indices_validos and rect.collidepoint(pos):
                            return str(indice + 1)
            self.clock.tick(30)

    def mostrar_game_over(self, ganador):
        """Pantalla de fin de partida. Muestra el ganador y los roles de todos."""
        while True:
            self.screen.fill((20, 20, 20))
            titulo = self.bold_font.render("¡FIN DE LA PARTIDA!", True, (255, 215, 0))
            self.screen.blit(titulo, (self.size[0] // 2 - titulo.get_width() // 2, 60))
            ganador_txt = self.font.render(f"Ganador: {ganador}", True, (255, 255, 100))
            self.screen.blit(ganador_txt, (self.size[0] // 2 - ganador_txt.get_width() // 2, 110))

            if self.juego:
                y = 170
                encabezado = self.bold_font.render("Jugadores:", True, (200, 200, 200))
                self.screen.blit(encabezado, (self.size[0] // 2 - encabezado.get_width() // 2, y))
                y += 30
                for j in self.juego.jugadores:
                    estado = "VIVO" if not j.muerto else "MUERTO"
                    color = (100, 220, 100) if not j.muerto else (180, 80, 80)
                    linea = f"{j.nombre} — {j.personaje.nombre} — {j.rol} — {estado}"
                    surf = self.small_font.render(linea, True, color)
                    self.screen.blit(surf, (self.size[0] // 2 - surf.get_width() // 2, y))
                    y += 26

            salir_rect = pygame.Rect(self.size[0] // 2 - 80, self.size[1] - 80, 160, 44)
            self._draw_boton("Salir", salir_rect, (180, 60, 60), (100, 0, 0))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if salir_rect.collidepoint(pygame.mouse.get_pos()):
                        pygame.quit()
                        sys.exit(0)
            self.clock.tick(30)

    def elegir_jugador(self, jugadores, text, jugadores_fuera_alcance=None):
        """Permite elegir un jugador haciendo clic directamente sobre su panel del tablero.
        :param jugadores: lista de Jugador entre los que se puede elegir.
        :param text: texto a mostrar en el panel inferior.
        :param jugadores_fuera_alcance: jugadores que no se pueden elegir por distancia;
            se marcan con un aviso en rojo pero no son clicables.
        :return: idJugador del jugador elegido.
        """
        ids_validos = {j.idJugador for j in jugadores}
        ids_fuera_alcance = {j.idJugador for j in jugadores_fuera_alcance or []}

        cancelar_rect = pygame.Rect(self.size[0] - LOG_W - 170, self.prompt_rect.y + 10, 150, 40)
        while True:
            panel_rects, _ = self._render_screen()
            pygame.draw.rect(self.screen, (230, 230, 230), self.prompt_rect)
            self._render_text(text, top=self.prompt_rect.y + 5, width=100)

            for id_jugador, rect in panel_rects.items():
                if id_jugador in ids_validos:
                    pygame.draw.rect(self.screen, (0, 180, 0), rect, 4)
                elif id_jugador in ids_fuera_alcance:
                    pygame.draw.rect(self.screen, (220, 0, 0), rect, 4)
                    aviso = self.small_font.render("FUERA DE ALCANCE", True, (220, 0, 0))
                    aviso_pos = (rect.centerx - aviso.get_width() // 2, rect.y - 18)
                    self.screen.blit(aviso, aviso_pos)

            self._draw_boton("Cancelar", cancelar_rect, (220, 180, 180))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    if cancelar_rect.collidepoint(pos):
                        return None
                    for id_jugador, rect in panel_rects.items():
                        if id_jugador in ids_validos and rect.collidepoint(pos):
                            return id_jugador
            self.clock.tick(30)
