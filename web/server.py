import os
import sys
import queue
import threading
import builtins

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, jsonify, request, render_template
from bang_game import info_extract, create_players, Juego
from flask_io import FlaskIO

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = "bang-secret-key"

# Sesión de juego única (un jugador local)
session = {
    "thread": None,
    "question_q": None,
    "answer_q": None,
    "log": [],
    "juego": None,
    "io": None,
    "pending": None,
    "running": False,
}


def _serialize_estado():
    """Serializa el estado completo del juego a un dict JSON-serializable.

    Incluye la lista de jugadores con sus atributos, la mano del jugador activo,
    la carta superior del montón de descartes y metadatos de la partida
    (ronda, turno actual, game_over, ganador).

    La referencia al montón de descartes se captura en una variable local para
    evitar la race condition en la que el hilo del juego vacía la lista entre
    la comprobación `if monton` y el acceso `monton[-1]`.

    Returns:
        dict: Estado serializado, o {} si la partida aún no ha iniciado.
    """
    juego = session["juego"]
    io = session["io"]
    if not juego:
        return {}

    n = len(juego.jugadores)
    turno_actual = (juego.turno - 1) % n

    jugadores = []
    for j in juego.jugadores:
        jugadores.append({
            "id": j.idJugador,
            "nombre": j.nombre,
            "personaje": j.personaje.nombre,
            "rol": j.rol if (j.muerto or j.rol == "Sheriff") else "?",
            "vidas": j.vidas,
            "vidasMax": j.vidasMax,
            "muerto": j.muerto,
            "arma": j.arma,
            "distancia": j.distancia,
            "estados": {
                "carcel": j.carcel,
                "mustang": j.mustang,
                "barril": j.barril,
                "dinamita": j.dinamita,
                "miraTelescopica": j.miraTelescopica,
                "volcanic": j.volcanic,
            },
            "numCartas": len(j.cartasMano),
            "cartasEquipadas": [
                {"nombre": c.nombre, "idClase": c.idClase}
                for c in j.cartasEquipadas
            ],
        })

    current = io.current_jugador if io else None
    mano = []
    if current:
        mano = [
            {"nombre": c.nombre, "tipo": c.tipo, "idClase": c.idClase, "indice": i}
            for i, c in enumerate(current.cartasMano)
        ]

    # Carta top del descarte — leer referencia una sola vez para evitar race condition:
    # el hilo del juego puede hacer monton_descartes=[] entre el 'if' y el '[-1]'
    descarte_top = None
    try:
        monton = juego.monton_descartes  # referencia local: segura aunque el atributo cambie
        if monton:
            c = monton[-1]
            descarte_top = {"nombre": c.nombre, "palo": getattr(c, "palo", ""), "numero": getattr(c, "numero", "")}
    except (IndexError, AttributeError):
        pass

    return {
        "jugadores": jugadores,
        "ronda": juego.ronda,
        "turno_actual": turno_actual,
        "current_jugador_id": current.idJugador if current else None,
        "game_over": juego.game_over,
        "ganador": juego.ganador,
        "descarte_top": descarte_top,
    }


def _run_game(num_players, nombres):
    """Punto de entrada del hilo de juego.

    Carga los datos del mazo, personajes y roles; crea los jugadores y lanza
    `juego.partida()`. Parchea `builtins.print` para capturar el log visible
    en el frontend. Cualquier excepción queda registrada en `session["log"]`
    y `session["error"]`.
    """
    baraja, personajes, roles = info_extract(
        os.path.join(BASE_DIR, "cartas.csv"),
        os.path.join(BASE_DIR, "personajes.txt"),
        os.path.join(BASE_DIR, "roles.txt"),
    )

    io = session["io"]

    orig_print = builtins.print
    def patched_print(*args, **kwargs):
        orig_print(*args, **kwargs)
        msg = " ".join(str(a) for a in args).strip()
        if msg:
            session["log"].append(msg)
            if len(session["log"]) > 300:
                session["log"].pop(0)
    builtins.print = patched_print

    try:
        jugadores = create_players(num_players, nombres, personajes, roles, io=io)
        juego = Juego(jugadores, baraja, io=io)
        session["juego"] = juego
        io.set_game(juego)
        juego.partida()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        session["log"].append(f"💥 ERROR: {e}")
        for line in tb.splitlines():
            session["log"].append(line)
        orig_print(tb)
        session["error"] = str(e)
    finally:
        builtins.print = orig_print
        session["running"] = False


# ------------------------------------------------------------------ rutas

@app.route("/")
def index():
    """Sirve el frontend HTML (index.html)."""
    return render_template("index.html")


@app.route("/nueva_partida", methods=["POST"])
def nueva_partida():
    """Inicia una nueva partida en un hilo daemon.

    Espera JSON con ``num_players`` (int) y ``nombres`` (list[str]).
    Resetea la sesión, crea las colas de comunicación y arranca el hilo del juego.

    Returns:
        JSON: ``{"ok": true}``
    """
    data = request.json
    num_players = int(data["num_players"])
    nombres = data["nombres"]

    # Resetear sesión
    session["log"] = []
    session["pending"] = None
    session["juego"] = None
    session["running"] = True
    session["error"] = None

    q = queue.Queue()
    a = queue.Queue()
    session["question_q"] = q
    session["answer_q"] = a

    io = FlaskIO(q, a, session["log"])
    session["io"] = io

    t = threading.Thread(target=_run_game, args=(num_players, nombres), daemon=True)
    session["thread"] = t
    t.start()

    return jsonify({"ok": True})


@app.route("/estado")
def estado():
    """Devuelve el estado actual del juego y la pregunta pendiente (si la hay).

    El cliente hace polling a este endpoint cada 200 ms. Si el hilo del juego
    puso una nueva pregunta en ``question_q``, se mueve a ``session["pending"]``
    para que el cliente la consuma.

    Returns:
        JSON: ``{estado, pregunta, log, running, error}``
    """
    q = session.get("question_q")
    # Recoge la pregunta pendiente si el juego acaba de poner una nueva
    if q and session["pending"] is None:
        try:
            session["pending"] = q.get_nowait()
        except queue.Empty:
            pass

    return jsonify({
        "estado": _serialize_estado(),
        "pregunta": session["pending"],
        "log": session["log"][-50:],
        "running": session["running"],
        "error": session.get("error"),
    })


@app.route("/accion", methods=["POST"])
def accion():
    """Recibe la respuesta del cliente y la entrega al hilo del juego.

    Espera JSON con ``valor`` (str). El valor se pone en ``answer_q`` y
    ``session["pending"]`` se limpia para que el frontend sepa que la pregunta
    fue respondida.

    Returns:
        JSON: ``{"ok": true}``
    """
    data = request.json
    valor = data.get("valor")

    a = session.get("answer_q")
    if a:
        a.put(str(valor) if valor is not None else "None")
        session["pending"] = None

    return jsonify({"ok": True})


@app.route("/debug")
def debug():
    """Endpoint de diagnóstico para inspeccionar el estado interno de la sesión.

    Devuelve información de bajo nivel útil durante el desarrollo:
    estado del hilo, jugador activo, tamaño de la cola de preguntas y últimas
    líneas del log. No se usa en producción.

    Returns:
        JSON: estado interno de la sesión.
    """
    io = session.get("io")
    return jsonify({
        "running": session.get("running"),
        "error": session.get("error"),
        "pending": session.get("pending"),
        "juego_ok": session.get("juego") is not None,
        "current_jugador": io.current_jugador.nombre if io and io.current_jugador else None,
        "mano_size": len(io.current_jugador.cartasMano) if io and io.current_jugador else 0,
        "q_size": session["question_q"].qsize() if session.get("question_q") else 0,
        "log_tail": session["log"][-10:],
    })


if __name__ == "__main__":
    app.run(debug=False, threaded=True, port=5000)
