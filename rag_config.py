"""Configuración compartida entre el script de ingesta (scripts/ingest_rules.py)
y el chat RAG (web/rag_chat.py). Vive en la raíz del proyecto para que ambos
puedan importarla sin duplicar constantes que deben coincidir siempre
(sobre todo EMBEDDING_MODEL: el modelo usado para indexar debe ser el mismo
que el usado para consultar, o los vectores no son comparables).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "docs" / "rules_source.pdf"
CHUNKS_PATH = BASE_DIR / "data" / "rules_chunks.json"
CHROMA_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "bang_reglas"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
