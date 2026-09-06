"""Entrena el clasificador "¿jugaría la heurística esta carta?" con
XGBoost sobre una muestra del dataset de la Fase 4.

En la comparación de las 3 librerías, XGBoost salió ganando claramente
frente al RandomForest de sklearn: mejor accuracy/AUC, modelo ~600x más
pequeño (1.3MB vs 809MB) y ~10x más rápido de entrenar — ver el docstring
de dl_bot.py para la tabla completa.

Uso:
    python sim/train_xgboost.py --dataset dataset_shards --max-filas 3000000
"""
import argparse
import json
import os
import time

from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
import xgboost as xgb

from load_dataset import cargar_muestra

MODELO_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_xgboost.json")


def main():
    parser = argparse.ArgumentParser(description="Entrena el modelo XGBoost (Fase 4)")
    parser.add_argument("--dataset", required=True, help="Carpeta de shards generada por collect_dataset.py")
    parser.add_argument("--max-filas", type=int, default=3_000_000)
    parser.add_argument("--out", default=MODELO_DEFECTO)
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--lr", type=float, default=0.1)
    args = parser.parse_args()

    print(f"Cargando hasta {args.max_filas} filas de {args.dataset} ...")
    t0 = time.perf_counter()
    X, y, columnas = cargar_muestra(args.dataset, max_filas=args.max_filas, seed=0)
    print(f"  {X.shape[0]} filas, {X.shape[1]} columnas, {100*y.mean():.1f}% positivas "
          f"({time.perf_counter()-t0:.1f}s)")

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.15, random_state=0, stratify=y)
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    print(f"Entrenando XGBoost (n_estimators={args.n_estimators}, max_depth={args.max_depth}) ...")
    t0 = time.perf_counter()
    clf = xgb.XGBClassifier(
        n_estimators=args.n_estimators, max_depth=args.max_depth, learning_rate=args.lr,
        n_jobs=-1, scale_pos_weight=pos_weight, eval_metric="logloss",
    )
    clf.fit(X_train, y_train)
    print(f"  entrenado en {time.perf_counter()-t0:.1f}s")

    proba_val = clf.predict_proba(X_val)[:, 1]
    pred_val = (proba_val >= 0.5).astype(int)
    acc = accuracy_score(y_val, pred_val)
    auc = roc_auc_score(y_val, proba_val)
    print(f"Validación: accuracy={acc:.4f} auc={auc:.4f}")

    clf.save_model(args.out)
    with open(args.out + ".columnas.json", "w", encoding="utf-8") as f:
        json.dump(columnas, f, ensure_ascii=False)
    print(f"Modelo guardado en {args.out}")


if __name__ == "__main__":
    main()
