"""Evalúa el retrieval del chat RAG con un set de preguntas de prueba.

Sin esto, "mejorar el RAG" son solo intuiciones — es la pieza que enseña el
curso "Retrieval Augmented Generation" (DeepLearning.AI) y que un RAG
casero suele saltarse. Mide, para cada pregunta, si el fragmento correcto
del reglamento aparece entre los recuperados (hit rate) y en qué posición
(MRR), y compara tres modos de recuperación para ver el efecto real de
cada técnica:

  - vectorial      : solo embeddings (línea base, lo que había antes)
  - hibrido         : + BM25 y fusión RRF
  - hibrido+rerank  : + reranking con cross-encoder (pipeline en producción)

Uso:
    python scripts/eval_retrieval.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import retrieval

# (pregunta, id del fragmento correcto). Cubre a propósito preguntas muy
# literales (favorecen BM25), preguntas parafraseadas (favorecen embeddings)
# y nombres con apodos/comillas para comprobar que el troceado es robusto.
CASOS_DE_PRUEBA = [
    ("¿Qué hace la carta Barril?", "chunk_023"),
    ("¿Para qué sirve la Mira Telescópica?", "chunk_021"),
    ("¿Cómo funciona la Dinamita?", "chunk_025"),
    ("¿Qué efecto tiene el Duelo?", "chunk_019"),
    ("¿Cómo recupero un punto de vida?", "chunk_010"),  # Cerveza, en paráfrasis
    ("¿Cómo le quito el arma a otro jugador?", "chunk_015"),  # ¡Pánico!
    ("¿Puedo jugar más de una carta Bang en mi turno?", "chunk_009"),
    ("¿Qué pasa si estoy en la Cárcel al empezar mi turno?", "chunk_024"),
    ("¿El Mustang aumenta o reduce la distancia a la que me ven?", "chunk_020"),
    ("¿Cuántas cartas robo al empezar mi turno?", "chunk_004"),  # La partida
    ("¿Cómo se prepara la partida antes de empezar a jugar?", "chunk_003"),
    ("¿Cuándo termina la partida y quién gana?", "chunk_005"),
    ("¿Qué habilidad especial tiene Jesse Jones?", "chunk_030"),
    ("¿Cuántos puntos de vida tiene El Gringo?", "chunk_029"),
    ("¿Qué hace Kit Carlson en su turno?", "chunk_032"),
    ("¿Cuál es la habilidad de Slab el Asesino?", "chunk_038"),
    ("¿Qué poder tiene Willy el Niño?", "chunk_041"),
    ("¿Qué le pasa a la mano de Buitre Sam cuando eliminan a otro jugador?", "chunk_040"),
    ("¿Qué significan los símbolos que aparecen en las cartas?", "chunk_012"),
    ("¿Cómo funciona desenfundar?", "chunk_022"),
    ("¿Qué diferencia hay entre el Sheriff y el Renegado?", "chunk_002"),  # Objetivo del juego
]

MODOS = {
    "vectorial          ": dict(hybrid=False, rerank=False),
    "hibrido (BM25+RRF) ": dict(hybrid=True, rerank=False),
    "hibrido+rerank      ": dict(hybrid=True, rerank=True),
}

K_MAX = 10  # nº de candidatos que se recuperan por pregunta para medir hit-rate@1/4/10


def evaluar_modo(nombre: str, opciones: dict) -> dict:
    aciertos_en_1 = 0
    aciertos_en_4 = 0
    aciertos_en_10 = 0
    reciprocal_ranks = []

    for pregunta, id_esperado in CASOS_DE_PRUEBA:
        resultados = retrieval.recuperar(pregunta, k_final=K_MAX, **opciones)
        ids_recuperados = [r["id"] for r in resultados]

        if id_esperado in ids_recuperados[:1]:
            aciertos_en_1 += 1
        if id_esperado in ids_recuperados[:4]:
            aciertos_en_4 += 1
        if id_esperado in ids_recuperados[:10]:
            aciertos_en_10 += 1

        if id_esperado in ids_recuperados:
            rank = ids_recuperados.index(id_esperado) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    n = len(CASOS_DE_PRUEBA)
    return {
        "hit@1": aciertos_en_1 / n,
        "hit@4": aciertos_en_4 / n,
        "hit@10": aciertos_en_10 / n,
        "mrr": sum(reciprocal_ranks) / n,
    }


def main() -> None:
    print(f"Evaluando retrieval con {len(CASOS_DE_PRUEBA)} preguntas de prueba...\n")

    filas = []
    for nombre, opciones in MODOS.items():
        metricas = evaluar_modo(nombre, opciones)
        filas.append((nombre, metricas))
        print(
            f"{nombre}  hit@1={metricas['hit@1']:.0%}  hit@4={metricas['hit@4']:.0%}  "
            f"hit@10={metricas['hit@10']:.0%}  MRR={metricas['mrr']:.2f}"
        )

    print("\nhit@k = % de preguntas en las que el fragmento correcto está entre los")
    print("        k primeros recuperados. MRR = 1/posición media del fragmento correcto")
    print("        (1.0 = siempre en el puesto 1; 0.0 = nunca aparece).")


if __name__ == "__main__":
    main()
