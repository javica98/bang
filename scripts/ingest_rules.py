"""Pipeline de ingesta del reglamento de BANG! para el chat RAG.

Lee docs/rules_source.pdf, lo trocea en fragmentos con sentido (una carta
especial, un personaje, una sección general de reglas), genera sus
embeddings con un modelo local y los guarda en un Chroma persistente en
data/chroma/. Se ejecuta a mano cada vez que cambie el PDF fuente:

    python scripts/ingest_rules.py
"""
import re
import sys
import json
import unicodedata
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag_config import PDF_PATH, CHUNKS_PATH, CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

# Títulos de sección de nivel superior, tal y como aparecen entre llaves
# "{ ... }" en el diseño del PDF. Definen los grandes bloques del reglamento.
TOP_LEVEL_HEADERS = [
    "Contenidos",
    "Objetivo del juego",
    "Preparación",
    "La partida",
    "Final de la partida",
    "Nueva partida",
    "Las cartas",
    "Los Personajes",
    "Y recuerda",
    "Nota",
    "Créditos",
]

# Subtítulos de carta dentro de la sección "Las cartas". Están en negrita en
# el PDF pero pypdf no conserva el formato, así que se listan explícitamente
# en el orden en que aparecen en este reglamento.
CARD_SUBHEADERS = [
    "Armas",
    "Volcanic",
    "¡BANG! y ¡Fallaste!",
    "Los símbolos de las cartas",
    "Cerveza",
    "Saloon",
    "Diligencia y Wells Fargo",
    "Almacén",
    "¡Pánico!",
    "La Ingenua Explosiva",
    "Ametralladora Gatling",
    "¡Indios!",
    "Duelo",
    "Mustang",
    "Mira Telescópica",
    "¡Desenfunda!",
    "Barril",
    "Cárcel",
    "Dinamita",
]

FOOTER_RE = re.compile(r"BANG_RULES_ES\.indd.*")
# Ruido típico de las cajas de ilustración: llaves vacías "{}" (marcador de
# icono sin texto) y líneas que sólo contienen un número de página suelto.
RUIDO_RE = re.compile(r"^\s*(\{\s*\}|\d{1,3})\s*$", re.MULTILINE)
# El PDF usa comillas tipográficas (" ") en apodos como Slab "el Asesino",
# así que la clase de caracteres del nombre debe incluirlas junto a las rectas.
PERSONAJE_RE = re.compile(
    r"([A-ZÁÉÍÓÚÑ“][\wÀ-ÿ'\"“”.\- ]{2,35}?) \((\d+) puntos? de vida\):\s*"
)


def extraer_texto(pdf_path: Path) -> str:
    """Extrae y normaliza el texto de todas las páginas del PDF."""
    reader = PdfReader(str(pdf_path))
    paginas = []
    for page in reader.pages:
        texto = page.extract_text() or ""
        texto = unicodedata.normalize("NFKC", texto)
        texto = FOOTER_RE.sub("", texto)
        texto = RUIDO_RE.sub("", texto)
        paginas.append(texto)
    texto_completo = "\n".join(paginas)
    return re.sub(r"\n{2,}", "\n", texto_completo)


def dividir_por_secciones(texto: str) -> list[tuple[str, str]]:
    """Divide el texto completo en (titulo_seccion, contenido) usando los
    encabezados "{ Título }" que marcan los grandes bloques del reglamento.
    """
    patron = re.compile(r"\{\s*([^{}]{2,60}?)\s*\}")
    posiciones = [(m.start(), m.end()) for m in patron.finditer(texto)]
    if not posiciones:
        return [("Reglamento", texto)]

    secciones = []
    for i, (inicio, fin) in enumerate(posiciones):
        siguiente_inicio = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(texto)
        contenido = texto[fin:siguiente_inicio].strip()
        titulo = TOP_LEVEL_HEADERS[i] if i < len(TOP_LEVEL_HEADERS) else f"Sección {i + 1}"
        secciones.append((titulo, contenido))

    # Texto antes del primer encabezado (portada/introducción)
    intro = texto[: posiciones[0][0]].strip()
    if intro:
        secciones.insert(0, ("Introducción", intro))

    return secciones


def dividir_seccion_cartas(contenido: str) -> list[tuple[str, str]]:
    """Trocea la sección "Las cartas" en un fragmento por cada carta especial.

    CARD_SUBHEADERS ya está en el orden real en que aparecen los títulos en
    el reglamento. Se busca cada título avanzando un cursor (nunca hacia
    atrás) en lugar de un `find()` independiente por título: el texto de
    cada carta suele mencionar por su nombre a otras cartas (p. ej. "Armas"
    menciona "¡Pánico!"), y buscar sin cursor encontraría esa mención
    cruzada en vez del encabezado real, desordenando los fragmentos.
    """
    posiciones = []
    cursor = 0
    for titulo in CARD_SUBHEADERS:
        idx = contenido.find(titulo, cursor)
        if idx != -1:
            posiciones.append((idx, titulo))
            cursor = idx + len(titulo)

    fragmentos = []
    for i, (inicio, titulo) in enumerate(posiciones):
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(contenido)
        texto = contenido[inicio:fin].strip()
        if texto:
            fragmentos.append((titulo, texto))
    return fragmentos or [("Las cartas", contenido)]


def dividir_seccion_personajes(contenido: str) -> list[tuple[str, str]]:
    """Trocea la sección "Los Personajes" en un fragmento por personaje,
    detectando el patrón "Nombre (N puntos de vida): ..." de cada entrada.
    """
    matches = list(PERSONAJE_RE.finditer(contenido))
    if not matches:
        return [("Los Personajes", contenido)]

    fragmentos = []
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(contenido)
        texto = contenido[m.start():fin].strip()
        fragmentos.append((m.group(1).strip(), texto))
    return fragmentos


def construir_chunks(texto: str) -> list[dict]:
    secciones = dividir_por_secciones(texto)
    chunks = []
    for titulo, contenido in secciones:
        if not contenido or len(contenido.split()) < 5:
            continue
        if titulo == "Las cartas":
            for subtitulo, subtexto in dividir_seccion_cartas(contenido):
                chunks.append({"seccion": "Las cartas", "titulo": subtitulo, "texto": subtexto})
        elif titulo == "Los Personajes":
            for nombre, subtexto in dividir_seccion_personajes(contenido):
                chunks.append({"seccion": "Los Personajes", "titulo": nombre, "texto": subtexto})
        else:
            chunks.append({"seccion": titulo, "titulo": titulo, "texto": contenido})

    for i, chunk in enumerate(chunks):
        chunk["id"] = f"chunk_{i:03d}"
    return chunks


def guardar_chunks(chunks: list[dict]) -> None:
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHUNKS_PATH.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")


def indexar_en_chroma(chunks: list[dict]) -> None:
    import chromadb
    from sentence_transformers import SentenceTransformer

    print(f"Cargando modelo de embeddings ({EMBEDDING_MODEL})...")
    modelo = SentenceTransformer(EMBEDDING_MODEL)

    textos = [f"{c['titulo']}\n{c['texto']}" for c in chunks]
    print(f"Generando embeddings para {len(textos)} fragmentos...")
    embeddings = modelo.encode(textos, show_progress_bar=True).tolist()

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    client.delete_collection(COLLECTION_NAME) if COLLECTION_NAME in [
        c.name for c in client.list_collections()
    ] else None
    coleccion = client.create_collection(COLLECTION_NAME)

    coleccion.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["texto"] for c in chunks],
        metadatas=[{"seccion": c["seccion"], "titulo": c["titulo"]} for c in chunks],
    )
    print(f"Indexados {len(chunks)} fragmentos en {CHROMA_DIR}")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"No se encuentra el PDF de reglas en {PDF_PATH}")

    print(f"Extrayendo texto de {PDF_PATH.name}...")
    texto = extraer_texto(PDF_PATH)

    print("Troceando en fragmentos...")
    chunks = construir_chunks(texto)
    print(f"{len(chunks)} fragmentos generados:")
    for c in chunks:
        print(f"  [{c['seccion']}] {c['titulo']} ({len(c['texto'].split())} palabras)")

    guardar_chunks(chunks)
    indexar_en_chroma(chunks)


if __name__ == "__main__":
    main()
