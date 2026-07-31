"""
Marathon test: plays 20 complete BANG games via the REST API.
"""
import requests
import time
import sys
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

BASE = "http://localhost:5000"
TARGET = 20
MAX_STEPS = 600
POLL_INTERVAL = 0.08   # 80 ms
POLL_ATTEMPTS = 200    # 16 s max per step


def send(valor):
    requests.post(f"{BASE}/accion", json={"valor": valor}, timeout=5)


def get_state():
    return requests.get(f"{BASE}/estado", timeout=5).json()


def wait_for_clear(attempts=5):
    """Wait until pending question is cleared (answer consumed).

    Only a few polls — the game is fast enough that a new question may
    appear before we can see pending=None, so we don't wait long.
    """
    for _ in range(attempts):
        d = get_state()
        if d.get("error"):
            return d
        if d.get("pregunta") is None:
            return d
        time.sleep(0.05)
    return get_state()


def wait_for_question(attempts=POLL_ATTEMPTS):
    """Wait until a new question arrives (any type)."""
    for _ in range(attempts):
        d = get_state()
        if d.get("error"):
            return d
        if d.get("pregunta") is not None:
            return d
        time.sleep(POLL_INTERVAL)
    return {"timeout": True}


def play_game(game_id, num_players=4):
    names = ["Javi", "B2", "B3", "B4", "B5", "B6", "B7"][:num_players]
    requests.post(f"{BASE}/nueva_partida", json={"num_players": num_players, "nombres": names}, timeout=5)

    steps = 0
    bugs = []
    last_tipo = None   # track previous question type

    # Wait for first question
    d = wait_for_question()

    while steps < MAX_STEPS:
        if d.get("timeout"):
            bugs.append(f"TIMEOUT step {steps}")
            return {"result": "timeout", "steps": steps, "bugs": bugs}
        if d.get("error"):
            return {"result": "server_error", "steps": steps, "bugs": [d["error"]]}

        q = d.get("pregunta")
        if q is None:
            bugs.append(f"No pregunta step {steps}")
            return {"result": "error", "steps": steps, "bugs": bugs}

        tipo = q["tipo"]
        steps += 1

        # Debug: log each step
        validos_log = q.get("jugadores_validos", [])
        opts_log = q.get("opciones", [])
        texto_log = q.get("texto", "")[:50]
        print(f"    step {steps}: tipo={tipo} validos={validos_log} opts={opts_log} texto={texto_log!r}", flush=True)

        if tipo == "game_over":
            return {"result": "ok", "steps": steps, "bugs": bugs}

        # --- decide answer ---
        if tipo == "elegir_personaje":
            valor = "A"

        elif tipo == "elegir_carta":
            # Play one card per turn: if we just resolved elegir_jugador, end turn
            # to avoid Volcanic infinite loops. Otherwise try to play a Bang.
            if last_tipo == "elegir_jugador":
                valor = "FIN"
            else:
                mano = q.get("mano", [])
                opciones = set(q.get("opciones", []))
                elegida = next(
                    (c for c in mano if str(c["indice"] + 1) in opciones and c["idClase"] != 12),
                    None
                )
                valor = str(elegida["indice"] + 1) if elegida else "FIN"

        elif tipo == "elegir_jugador":
            validos = q.get("jugadores_validos", [])
            if validos:
                valor = str(validos[0])
            else:
                bugs.append(f"elegir_jugador sin validos paso {steps}")
                valor = "None"

        elif tipo == "prompt":
            opts = q.get("opciones", [])
            valor = opts[0] if opts else "SI"

        elif tipo == "elegir_lucky_duke":
            valor = "0"
        elif tipo == "elegir_kit_carlson":
            valor = "0"
        elif tipo == "elegir_almacen_carta":
            valor = "0"
        elif tipo == "elegir_robo_pedro":
            valor = "NO"
        elif tipo == "elegir_carta_rival":
            valor = "mano:0"
        elif tipo == "elegir_robo_jesse":
            rivales = q.get("rivales", [])
            valor = str(rivales[0]) if rivales else "None"
        else:
            print(f"  [!] tipo desconocido: {tipo}", flush=True)
            valor = "None"

        # Send answer
        last_tipo = tipo
        send(valor)

        # Two-phase poll: wait for pending to clear, then wait for next question
        d = wait_for_clear()
        if d.get("error"):
            return {"result": "server_error", "steps": steps, "bugs": [d["error"]]}

        d = wait_for_question()

    return {"result": "max_steps", "steps": steps, "bugs": ["max steps reached"]}


def main():
    consecutive = 0
    total = 0

    print(f"Marathon test — objetivo: {TARGET} partidas limpias seguidas\n")

    while consecutive < TARGET:
        total += 1
        t0 = time.time()
        game = play_game(total, num_players=4)
        elapsed = time.time() - t0
        game["id"] = total
        game["elapsed"] = round(elapsed, 1)

        clean = game["result"] == "ok" and len(game["bugs"]) == 0
        consecutive = consecutive + 1 if clean else 0

        status = "OK" if clean else "FAIL"
        print(f"  {status} G{total}: {game['result']} | {game['steps']} pasos | {game['elapsed']}s | racha {consecutive}/{TARGET}", flush=True)
        if game["bugs"]:
            for b in game["bugs"]:
                print(f"      BUG: {b}", flush=True)

        if total > TARGET * 3:
            print(f"\nDemasiados fallos ({total} partidas, solo {consecutive} racha). Abortando.")
            sys.exit(1)

    print(f"\n[PASS] {TARGET} partidas limpias seguidas en {total} intentos!")


if __name__ == "__main__":
    main()
