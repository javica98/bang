"""Entrena el clasificador "¿jugaría la heurística esta carta?" con
scikit-learn (RandomForest) sobre una muestra del dataset de la Fase 4.

Uso:
    python sim/train_sklearn.py --dataset dataset_shards --max-filas 3000000
"""
import argparse
import json
import os
import time

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from load_dataset import cargar_muestra

MODELO_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_sklearn.joblib")


def main():
    parser = argparse.ArgumentParser(description="Entrena el modelo sklearn (Fase 4)")
    parser.add_argument("--dataset", required=True, help="Carpeta de shards generada por collect_dataset.py")
    parser.add_argument("--max-filas", type=int, default=3_000_000)
    parser.add_argument("--out", default=MODELO_DEFECTO)
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=18)
    args = parser.parse_args()

    print(f"Cargando hasta {args.max_filas} filas de {args.dataset} ...")
    t0 = time.perf_counter()
    X, y, columnas = cargar_muestra(args.dataset, max_filas=args.max_filas, seed=0)
    print(f"  {X.shape[0]} filas, {X.shape[1]} columnas, {100*y.mean():.1f}% positivas "
          f"({time.perf_counter()-t0:.1f}s)")

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.15, random_state=0, stratify=y)

    print(f"Entrenando RandomForest (n_estimators={args.n_estimators}, max_depth={args.max_depth}) ...")
    t0 = time.perf_counter()
    clf = RandomForestClassifier(
        n_estimators=args.n_estimators, max_depth=args.max_depth,
        n_jobs=-1, random_state=0, class_weight="balanced",
    )
    clf.fit(X_train, y_train)
    print(f"  entrenado en {time.perf_counter()-t0:.1f}s")

    proba_val = clf.predict_proba(X_val)[:, 1]
    pred_val = (proba_val >= 0.5).astype(int)
    acc = accuracy_score(y_val, pred_val)
    auc = roc_auc_score(y_val, proba_val)
    print(f"Validación: accuracy={acc:.4f} auc={auc:.4f}")

    joblib.dump(clf, args.out)
    with open(args.out + ".columnas.json", "w", encoding="utf-8") as f:
        json.dump(columnas, f, ensure_ascii=False)
    print(f"Modelo guardado en {args.out}")


if __name__ == "__main__":
    main()
