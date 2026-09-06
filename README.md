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
- **Chat de reglas con RAG**: pregunta en lenguaje natural sobre las reglas del juego

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

### Chat de reglas (RAG)

El botón **REGLAS** de la partida abre un chat que responde preguntas sobre las
reglas de BANG! basándose en el reglamento oficial (`docs/rules_source.pdf`).

1. Copia `.env.example` a `.env` y añade tu clave de la API de Anthropic:
   ```bash
   cp .env.example .env
   # edita .env y pon ANTHROPIC_API_KEY=sk-ant-...
   ```
2. Genera el índice de búsqueda semántica (solo hace falta una vez, o cada
   vez que cambie `docs/rules_source.pdf`). Descarga un modelo de embeddings
   (~470 MB) la primera vez que se ejecuta:
   ```bash
   python scripts/ingest_rules.py
   ```
3. Arranca el servidor normalmente (`cd web && python server.py`) y usa el
   botón REGLAS durante la partida.

El chat solo responde preguntas relacionadas con BANG! y se basa únicamente en
los fragmentos del reglamento recuperados para cada pregunta (RAG), no en
conocimiento general del modelo.

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
├── rag_config.py         # Constantes compartidas del chat RAG (rutas, modelo)
├── docs/
│   └── rules_source.pdf  # Reglamento oficial (fuente del chat de reglas)
├── scripts/
│   └── ingest_rules.py   # Extrae, trocea e indexa el PDF en Chroma
├── data/                 # Índice vectorial generado (data/chroma/, gitignored)
├── web/
│   ├── server.py         # Servidor Flask
│   ├── flask_io.py       # Adaptador IO para la web
│   ├── rag_chat.py       # Recuperación + llamada a Claude para el chat de reglas
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

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Los tests viven en `tests/` y cubren, de momento, las clases de estado (`ClasesAux.py`)
y el cálculo de distancia (`Juego.distancia`). `tests/conftest.py` incluye un `FakeIO`
(doble de test que responde con valores prescritos en vez de bloquear en `input()`) y
fábricas (`make_carta`, `make_jugador`, `make_juego`, …) para montar partidas de prueba
sin depender de `cartas.csv`/`personajes.txt`/`roles.txt`.

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
