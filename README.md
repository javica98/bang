# BANG! 🤠

Implementación del juego de cartas **BANG!** en Python con interfaz web.

Los jugadores asumen roles secretos — Sheriff, Ayudante, Forajido o Renegado — y se enfrentan en una partida de faroeste donde el objetivo del Sheriff es eliminar a todos los forajidos, mientras éstos intentan acabar con él primero.

---

## Características

- **2–7 jugadores** en la misma máquina (hot-seat)
- **15 personajes** con poderes únicos: Willy the Kid, Slab the Killer, Lucky Duke, Kit Carlson…
- **22 tipos de cartas**: Bang, Fallaste, Cerveza, Dinamita, Cárcel, Almacén, Duelo…
- Interfaz web con diseño **Retro Pixel-Art** (Dust & Dithering)
- Versión alternativa en **Pygame** (modo consola local)

---

## Instalación

```bash
git clone https://github.com/TU_USUARIO/bang.git
cd bang
pip install -r requirements.txt
```

---

## Ejecutar

### Versión Web (recomendada)

```bash
cd web
python server.py
```

Abre el navegador en **http://localhost:5000**

### Versión Pygame

```bash
python run_bang_pygame.py
```

---

## Estructura del proyecto

```
bang/
├── bang_game.py          # Motor del juego (reglas, turnos, cartas)
├── ClasesAux.py          # Clases Jugador, Carta, Personaje
├── cartas.csv            # Definición de las 80 cartas
├── personajes.txt        # Definición de los 16 personajes
├── roles.txt             # Roles por número de jugadores
├── web/
│   ├── server.py         # Servidor Flask
│   ├── flask_io.py       # Adaptador IO para la web
│   └── templates/
│       └── index.html    # Frontend (HTML + CSS + JS)
├── bang_pygame_io.py     # Adaptador IO para Pygame
└── run_bang_pygame.py    # Punto de entrada Pygame
```

---

## Cómo jugar

1. Inicia el servidor y abre http://localhost:5000
2. Elige el número de jugadores (4–7) e introduce los nombres
3. Cada jugador elige su personaje en secreto
4. Juega por turnos: roba 2 cartas, úsalas, descarta hasta tu límite de vida
5. El **Sheriff** gana si elimina a todos los Forajidos y al Renegado
6. Los **Forajidos** ganan si matan al Sheriff
7. El **Renegado** gana si es el último superviviente

---

## Tecnologías

- Python 3.10+
- Flask (servidor web)
- HTML / CSS / JavaScript vanilla (sin frameworks)
- Pygame (interfaz alternativa)

---

## Licencia

Este proyecto es una implementación no oficial con fines educativos.  
BANG! es marca registrada de **daVinci Editrice**.
