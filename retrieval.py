"""Recuperación híbrida para el chat RAG de reglas de BANG!.

Implementa, aplicadas a nuestro corpus de reglas, las técnicas centrales del
curso "Retrieval Augmented Generation" (DeepLearning.AI / Zain Hasan):

1. Búsqueda por palabras clave (BM25) — acierta nombres propios exactos
   ("Barril", "Mira Telescópica") que la búsqueda semántica a veces difumina.
2. Búsqueda vectorial (embeddings) — capta el significado aunque la
   pregunta use otras palabras ("¿cómo recupero vida?" -> Cerveza).
3. Reciprocal Rank Fusion (RRF) — combina ambos rankings sin tener que
   decidir a mano un peso entre "léxico" y "semántico".
4. Reranking con cross-encoder — relee cada candidato junto a la pregunta
   (no por separado, como los embeddings) para ordenar con más precisión
   los top-N antes de quedarnos con los pocos que van al LLM.

Es un módulo compartido: lo usan tanto el chat en producción
(web/rag_chat.py) como el script de evaluación (scripts/eval_retrieval.py),
para que ambos midan y usen exactamente el mismo pipeline.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_config import CHUNKS_PATH, CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
RRF_K = 60  # constante estándar de Reciprocal Rank Fusion (Cormack et al. 2009)
N_CANDIDATOS = 12  # cuántos candidatos llegan a la fase de fusión/reranking

_chunks_cache = None
_bm25 = None
_embedder = None
_collection = None
_reranker = None


def _tokenizar(texto: str) -> list[str]:
    return re.findall(r"\w+", texto.lower())


def _cargar_chunks() -> list[dict]:
    global _chunks_cache
    if _chunks_cache is None:
        if not CHUNKS_PATH.exists():
            raise RuntimeError(
                "No existen fragmentos de reglas. Ejecuta 'python scripts/ingest_rules.py' primero."
            )
        _chunks_cache = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    return _chunks_cache


def _get_bm25():
    global _bm25
    if _bm25 is None:
        from rank_bm25 import BM25Okapi
        corpus = [f"{c['titulo']} {c['texto']}" for c in _cargar_chunks()]
        _bm25 = BM25Okapi([_tokenizar(doc) for doc in corpus])
    return _bm25


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
                "No existe el índice vectorial. Ejecuta 'python scripts/ingest_rules.py' primero."
            )
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker


def _ranking_vectorial(pregunta: str, n: int) -> list[str]:
    """IDs de fragmento ordenados por similitud semántica (embeddings + Chroma)."""
    # Comprueba primero que el índice existe (local, sin red) antes de cargar
    # el modelo de embeddings (que sí puede necesitar descargar pesos).
    coleccion = _get_collection()
    embedder = _get_embedder()
    query_embedding = embedder.encode([pregunta]).tolist()
    resultados = coleccion.query(query_embeddings=query_embedding, n_results=n)
    return resultados["ids"][0]


def _ranking_bm25(pregunta: str, n: int) -> list[str]:
    """IDs de fragmento ordenados por relevancia léxica (BM25)."""
    bm25 = _get_bm25()
    chunks = _cargar_chunks()
    puntuaciones = bm25.get_scores(_tokenizar(pregunta))
    orden = sorted(range(len(chunks)), key=lambda i: puntuaciones[i], reverse=True)
    return [chunks[i]["id"] for i in orden[:n]]


def fusion_rrf(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    """Combina varias listas ordenadas de IDs con Reciprocal Rank Fusion.

    score(doc) = suma, por cada ranking en el que aparece, de 1/(k + posición).
    Un documento que queda bien situado en varios rankings a la vez sube en
    el resultado combinado; no hace falta decidir a mano cuánto pesa BM25
    frente al embedding.
    """
    puntuaciones: dict[str, float] = {}
    for ranking in rankings:
        for posicion, doc_id in enumerate(ranking):
            puntuaciones[doc_id] = puntuaciones.get(doc_id, 0.0) + 1.0 / (k + posicion + 1)
    return sorted(puntuaciones, key=puntuaciones.get, reverse=True)


def recuperar(
    pregunta: str,
    k_final: int = 4,
    n_candidatos: int = N_CANDIDATOS,
    hybrid: bool = True,
    rerank: bool = True,
) -> list[dict]:
    """Recupera los k_final fragmentos más relevantes del reglamento para una pregunta.

    Pipeline por defecto: BM25 + vectorial -> fusión RRF -> reranking con
    cross-encoder -> top k_final. Los flags `hybrid`/`rerank` permiten
    desactivar cada etapa (usado por scripts/eval_retrieval.py para medir
    el impacto real de cada una por separado).
    """
    chunks_por_id = {c["id"]: c for c in _cargar_chunks()}

    if hybrid:
        candidatos_ids = fusion_rrf([
            _ranking_vectorial(pregunta, n_candidatos),
            _ranking_bm25(pregunta, n_candidatos),
        ])[:n_candidatos]
    else:
        candidatos_ids = _ranking_vectorial(pregunta, n_candidatos)

    candidatos = [chunks_por_id[doc_id] for doc_id in candidatos_ids if doc_id in chunks_por_id]

    if rerank and candidatos:
        reranker = _get_reranker()
        pares = [(pregunta, f"{c['titulo']}\n{c['texto']}") for c in candidatos]
        puntuaciones = reranker.predict(pares)
        candidatos = [
            c for _, c in sorted(zip(puntuaciones, candidatos), key=lambda x: x[0], reverse=True)
        ]

    return candidatos[:k_final]
