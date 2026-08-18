"""Lógica del chat RAG: recupera fragmentos relevantes del reglamento
(indexados por scripts/ingest_rules.py) y genera la respuesta con Claude.

Carga perezosa (lazy) del modelo de embeddings y de la colección de Chroma:
la primera pregunta tarda un poco más (se carga el modelo en memoria), las
siguientes son instantáneas porque quedan cacheados a nivel de módulo.
"""
import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag_config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

MODEL = "claude-haiku-4-5"
TOP_K = 4

SYSTEM_PROMPT = """Eres el asistente de reglas del juego de cartas BANG! (el juego \
del salvaje oeste, edición en español de daVinci Editrice / Edge Entertainment).

Tu único trabajo es responder preguntas sobre las reglas de BANG!: preparación de \
la partida, turnos, distancias, cartas (Armas, ¡Bang!, ¡Fallaste!, Cerveza, Barril, \
Cárcel, Dinamita, etc.) y personajes.

Reglas de tu comportamiento:
- Responde ÚNICAMENTE usando los fragmentos del reglamento que se te den como \
contexto en cada pregunta. No inventes reglas que no estén en esos fragmentos.
- Si la pregunta no tiene relación con BANG! (por ejemplo, temas generales, otros \
juegos, o cualquier otra cosa), responde amablemente que solo puedes ayudar con \
las reglas de BANG! y no contestes esa pregunta.
- Si los fragmentos de contexto no contienen la respuesta, dilo explícitamente en \
vez de adivinar.
- Responde en español, de forma breve y clara, como si le explicaras la regla a un \
jugador en mitad de la partida."""

_embedder = None
_collection = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _get_collection():
    global _collection
    if _collection is None:
        import chromadb
        if not CHROMA_DIR.exists():
            raise RuntimeError(
                "No existe el índice de reglas. Ejecuta 'python scripts/ingest_rules.py' primero."
            )
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def _recuperar_contexto(pregunta: str, k: int = TOP_K) -> list[dict]:
    """Busca en Chroma los k fragmentos del reglamento más relevantes para la pregunta."""
    # Comprueba primero que el índice existe (local, sin red) antes de cargar
    # el modelo de embeddings (que sí puede necesitar descargar pesos).
    coleccion = _get_collection()
    embedder = _get_embedder()
    query_embedding = embedder.encode([pregunta]).tolist()
    resultados = coleccion.query(query_embeddings=query_embedding, n_results=k)

    documentos = resultados["documents"][0]
    metadatas = resultados["metadatas"][0]
    return [
        {"titulo": meta["titulo"], "seccion": meta["seccion"], "texto": doc}
        for doc, meta in zip(documentos, metadatas)
    ]


def responder_pregunta(pregunta: str, historial: list[dict] | None = None) -> dict:
    """Responde una pregunta sobre las reglas de BANG! usando RAG.

    Args:
        pregunta: la pregunta del usuario.
        historial: turnos previos de la conversación, en formato
            [{"role": "user"|"assistant", "content": "..."}, ...], para
            permitir preguntas de seguimiento ("¿y si tiene un Mustang?").

    Returns:
        dict con "respuesta" (str) y "fuentes" (list[str], los títulos de
        los fragmentos usados, para mostrar de dónde sale la respuesta).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "respuesta": "El chat no está configurado: falta la variable de entorno ANTHROPIC_API_KEY.",
            "fuentes": [],
        }

    try:
        fragmentos = _recuperar_contexto(pregunta)
    except RuntimeError as e:
        return {"respuesta": str(e), "fuentes": []}

    contexto = "\n\n---\n\n".join(f"[{f['titulo']}]\n{f['texto']}" for f in fragmentos)
    mensaje_usuario = (
        f"Fragmentos del reglamento de BANG! relevantes para esta pregunta:\n\n"
        f"{contexto}\n\n---\n\nPregunta del jugador: {pregunta}"
    )

    mensajes = list(historial or []) + [{"role": "user", "content": mensaje_usuario}]

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=mensajes,
        )
    except anthropic.AuthenticationError:
        return {"respuesta": "La clave de la API de Anthropic no es válida.", "fuentes": []}
    except anthropic.RateLimitError:
        return {"respuesta": "Demasiadas preguntas seguidas, inténtalo de nuevo en unos segundos.", "fuentes": []}
    except anthropic.APIConnectionError:
        return {"respuesta": "No se ha podido conectar con el servicio de chat. Revisa tu conexión.", "fuentes": []}
    except anthropic.APIStatusError as e:
        return {"respuesta": f"Error del servicio de chat: {e.message}", "fuentes": []}

    texto = next((b.text for b in response.content if b.type == "text"), "")
    return {"respuesta": texto, "fuentes": [f["titulo"] for f in fragmentos]}
