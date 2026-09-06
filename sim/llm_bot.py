"""Bot LLM — Fase 3 del roadmap de IA.

Para cada decisión de "qué carta jugar", serializa el estado relevante de
la partida en un prompt (JSON + descripción + un par de ejemplos) y le
pide al modelo que elija una de las opciones válidas. Todo lo demás (a
quién apuntar, si esquivar, etc.) se delega al BotAI heurístico interno —
mismo alcance acotado que MCTSBotAI/DLBotAI, para no disparar una llamada
a la API por cada micro-decisión de la partida (una partida completa
puede tener 150-300+ decisiones).

Tres proveedores (`provider=...`), pensado para comparar entre ellos tal
como pide el roadmap:
    - "gemini" (por defecto): GEMINI_API_KEY o GOOGLE_API_KEY
    - "claude" (Anthropic):   ANTHROPIC_API_KEY
    - "groq":                 GROQ_API_KEY

Si la API falla, tarda demasiado, o responde algo que no es una opción
válida, esa decisión cae en la heurística como red de seguridad — se
registra en `self.metricas` para poder medir tasa de fallos, latencia y
coste tal como pide el roadmap. Los fallos transitorios (timeout, 429,
5xx) se reintentan un par de veces con una espera corta antes de rendirse.

Solo se revela al LLM lo que un jugador real vería: su propia mano y rol,
y de los rivales solo lo público (vidas, cartas equipadas, y el rol del
Sheriff, que siempre es visible). No hay sistema de creencias explícito
como en BotAI — el razonamiento sobre quién es sospechoso queda en manos
del propio modelo.
"""
import json
import os
import sys
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bot_ai import BotAI  # noqa: E402

TIMEOUT_S_DEFECTO = 10
REINTENTOS_DEFECTO = 2
ESPERA_REINTENTO_S = 1.5

MODELOS_DEFECTO = {
    "gemini": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
    "claude": os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
    "groq": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Un par de ejemplos cortos para anclar el formato de respuesta y las
# prioridades básicas (curarse si hay poca vida, atacar si hay enemigo a
# tiro) — igual que ya hace la heurística de Fase 1, pero en lenguaje
# natural para que el LLM parta de una idea razonable del juego.
EJEMPLOS_FEW_SHOT = """\
Ejemplo 1:
Estado: mis_vidas=1, mis_vidas_max=4, mi_mano=[{"opcion":"1","nombre":"Cerveza"},{"opcion":"2","nombre":"Bang"}]
Respuesta correcta: 1
(Con 1 vida de 4, curarse es más urgente que atacar — casi mueres si te atacan.)

Ejemplo 2:
Estado: mis_vidas=4, mis_vidas_max=4, mi_mano=[{"opcion":"1","nombre":"Bang"},{"opcion":"2","nombre":"Diligencia"}], hay un rival a tiro con pocas vidas
Respuesta correcta: 1
(A vida completa, con un enemigo al alcance, atacar suele valer más que robar cartas extra.)
"""


def _api_key(provider):
    if provider == "gemini":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if provider == "claude":
        return os.environ.get("ANTHROPIC_API_KEY")
    if provider == "groq":
        return os.environ.get("GROQ_API_KEY")
    raise ValueError(f"proveedor desconocido: {provider!r}")


class LLMBotAI:
    """IA para un bot concreto que delega "qué carta jugar" a un LLM."""

    def __init__(self, bot_id, provider="gemini", model=None, timeout_s=TIMEOUT_S_DEFECTO,
                 reintentos=REINTENTOS_DEFECTO):
        if provider not in ("gemini", "claude", "groq"):
            raise ValueError(f"provider debe ser 'gemini', 'claude' o 'groq', no {provider!r}")
        self.bot_id = bot_id
        self.provider = provider
        self.model = model or MODELOS_DEFECTO[provider]
        self.timeout_s = timeout_s
        self.reintentos = reintentos
        self._heuristico = BotAI(bot_id)
        self.metricas = []  # {latencia_s, tokens_entrada, tokens_salida, fallback, error, intentos}
        # Igual que MCTSBotAI: si la última acción elegida no cambió la
        # mano (no-op, p.ej. Fallaste fuera de una respuesta a Bang), se
        # descarta esa opción la próxima vez para no quedarse en bucle.
        self._ultima_eleccion = None
        self._acciones_fallidas = set()

    def observar(self, señal, actor_id):
        self._heuristico.observar(señal, actor_id)

    def decidir(self, pregunta, jugador, juego):
        if juego is not None:
            self._heuristico._inicializar(juego)
        if pregunta.get('tipo') == 'elegir_carta':
            return self._decidir_carta_llm(pregunta, jugador, juego)
        return self._heuristico.decidir(pregunta, jugador, juego)

    def _decidir_carta_llm(self, pregunta, jugador, juego):
        mano = pregunta.get('mano', [])
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

        prompt = self._construir_prompt(pregunta, jugador, juego, opciones)
        t0 = time.perf_counter()
        texto, tokens_in, tokens_out, error, intentos = self._llamar_con_reintentos(prompt)
        latencia = time.perf_counter() - t0

        elegido = self._extraer_opcion(texto, opciones)
        fallback = elegido is None
        if fallback:
            elegido = self._heuristico._elegir_carta(pregunta, jugador, juego)

        self.metricas.append({
            "latencia_s": round(latencia, 3),
            "tokens_entrada": tokens_in,
            "tokens_salida": tokens_out,
            "fallback": fallback,
            "error": error,
            "intentos": intentos,
        })
        self._ultima_eleccion = (elegido, len(mano))
        return elegido

    def _llamar_con_reintentos(self, prompt):
        llamar = {"gemini": self._llamar_gemini, "claude": self._llamar_claude, "groq": self._llamar_groq}[self.provider]
        ultimo_error = None
        for intento in range(1, self.reintentos + 2):  # intento inicial + reintentos
            texto, tokens_in, tokens_out, error, transitorio = llamar(prompt)
            if error is None:
                return texto, tokens_in, tokens_out, None, intento
            ultimo_error = error
            if not transitorio or intento == self.reintentos + 1:
                break
            time.sleep(ESPERA_REINTENTO_S)
        return None, 0, 0, ultimo_error, self.reintentos + 1

    @staticmethod
    def _extraer_opcion(texto, opciones):
        """Intenta encajar la respuesta del LLM con una opción válida.
        Devuelve None si no se puede (dispara el fallback heurístico).
        """
        if not texto:
            return None
        candidato = texto.strip().splitlines()[0].strip().strip(".\"'").upper()
        mapa = {op.upper(): op for op in opciones}
        if candidato in mapa:
            return mapa[candidato]
        # Tolerar respuestas con texto extra alrededor de la opción exacta.
        for token in candidato.replace(",", " ").split():
            if token in mapa:
                return mapa[token]
        return None

    def _construir_prompt(self, pregunta, jugador, juego, opciones):
        mi_rol = jugador.rol
        estado = {
            "mi_id": jugador.idJugador,
            "mi_rol_secreto": mi_rol,
            "mi_personaje": jugador.personaje.nombre,
            "mis_vidas": jugador.vidas,
            "mis_vidas_max": jugador.vidasMax,
            "mi_mano": [
                {"opcion": str(c['indice'] + 1), "nombre": c['nombre'], "tipo": c['tipo']}
                for c in pregunta.get('mano', [])
            ],
            "rivales": [
                {
                    "id": j.idJugador,
                    "vidas": j.vidas,
                    "vidas_max": j.vidasMax,
                    "muerto": j.muerto,
                    "rol_visible": "Sheriff" if j.rol == "Sheriff" else "desconocido",
                    "cartas_equipadas": [c.nombre for c in j.cartasEquipadas],
                }
                for j in juego.jugadores if j.idJugador != jugador.idJugador
            ],
        }
        instrucciones = (
            f"Eres un jugador de BANG! (rol secreto: {mi_rol}). {pregunta.get('texto', '')}\n"
            f"Ojo: no todas las cartas de tu mano son jugables ahora mismo (p.ej. ya usaste tu "
            f"Bang de este turno, o Fallaste solo se juega como respuesta a un Bang) — si no estás "
            f"seguro de que una jugada sea válida, prefiere FIN.\n\n"
            f"{EJEMPLOS_FEW_SHOT}\n"
            f"Responde ÚNICAMENTE con una de estas opciones exactas, sin explicación ni puntuación: "
            f"{', '.join(opciones)}."
        )
        return instrucciones + "\n\nEstado actual (JSON):\n" + json.dumps(estado, ensure_ascii=False)

    # ------------------------------------------------------------------ proveedores

    def _llamar_gemini(self, prompt):
        """Devuelve (texto, tokens_in, tokens_out, error, es_transitorio)."""
        api_key = _api_key("gemini")
        if not api_key:
            return None, 0, 0, "GEMINI_API_KEY / GOOGLE_API_KEY no configurada", False
        url = GEMINI_URL.format(model=self.model)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 20},
        }
        try:
            resp = requests.post(url, params={"key": api_key}, json=body, timeout=self.timeout_s)
            if resp.status_code == 429 or resp.status_code >= 500:
                return None, 0, 0, f"HTTP {resp.status_code}: {resp.text[:200]}", True
            resp.raise_for_status()
            data = resp.json()
            texto = data["candidates"][0]["content"]["parts"][0]["text"]
            uso = data.get("usageMetadata", {})
            return texto, uso.get("promptTokenCount", 0), uso.get("candidatesTokenCount", 0), None, False
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            return None, 0, 0, f"{type(e).__name__}: {e}", True
        except Exception as e:
            return None, 0, 0, f"{type(e).__name__}: {e}", False

    def _llamar_claude(self, prompt):
        api_key = _api_key("claude")
        if not api_key:
            return None, 0, 0, "ANTHROPIC_API_KEY no configurada", False
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 20,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(CLAUDE_URL, headers=headers, json=body, timeout=self.timeout_s)
            if resp.status_code == 429 or resp.status_code >= 500:
                return None, 0, 0, f"HTTP {resp.status_code}: {resp.text[:200]}", True
            resp.raise_for_status()
            data = resp.json()
            texto = "".join(bloque.get("text", "") for bloque in data.get("content", []))
            uso = data.get("usage", {})
            return texto, uso.get("input_tokens", 0), uso.get("output_tokens", 0), None, False
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            return None, 0, 0, f"{type(e).__name__}: {e}", True
        except Exception as e:
            return None, 0, 0, f"{type(e).__name__}: {e}", False

    def _llamar_groq(self, prompt):
        api_key = _api_key("groq")
        if not api_key:
            return None, 0, 0, "GROQ_API_KEY no configurada", False
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        body = {
            "model": self.model,
            "max_tokens": 20,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=self.timeout_s)
            if resp.status_code == 429 or resp.status_code >= 500:
                return None, 0, 0, f"HTTP {resp.status_code}: {resp.text[:200]}", True
            resp.raise_for_status()
            data = resp.json()
            texto = data["choices"][0]["message"]["content"]
            uso = data.get("usage", {})
            return texto, uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0), None, False
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            return None, 0, 0, f"{type(e).__name__}: {e}", True
        except Exception as e:
            return None, 0, 0, f"{type(e).__name__}: {e}", False
