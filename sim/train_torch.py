"""Entrena el clasificador "¿jugaría la heurística esta carta?" con
PyTorch (MLP pequeño) sobre una muestra del dataset de la Fase 4.

Uso:
    python sim/train_torch.py --dataset dataset_shards --max-filas 3000000
"""
import argparse
import json
import os
import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from load_dataset import cargar_muestra

MODELO_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_torch.pt")


class MLP(nn.Module):
    def __init__(self, n_entradas, ocultas=(128, 64)):
        super().__init__()
        capas = []
        anterior = n_entradas
        for n in ocultas:
            capas += [nn.Linear(anterior, n), nn.ReLU(), nn.Dropout(0.1)]
            anterior = n
        capas.append(nn.Linear(anterior, 1))
        self.red = nn.Sequential(*capas)

    def forward(self, x):
        return self.red(x).squeeze(-1)


def main():
    parser = argparse.ArgumentParser(description="Entrena el modelo PyTorch (Fase 4)")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--max-filas", type=int, default=3_000_000)
    parser.add_argument("--out", default=MODELO_DEFECTO)
    parser.add_argument("--epocas", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    print(f"Cargando hasta {args.max_filas} filas de {args.dataset} ...")
    t0 = time.perf_counter()
    X, y, columnas = cargar_muestra(args.dataset, max_filas=args.max_filas, seed=0)
    print(f"  {X.shape[0]} filas, {X.shape[1]} columnas, {100*y.mean():.1f}% positivas "
          f"({time.perf_counter()-t0:.1f}s)")

    # Normalización simple (media/desviación) — ayuda a la convergencia del MLP.
    media = X.mean(axis=0, keepdims=True)
    desv = X.std(axis=0, keepdims=True)
    desv[desv < 1e-6] = 1.0
    X = (X - media) / desv

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.15, random_state=0, stratify=y)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Entrenando MLP en {device} ...")
    modelo = MLP(X.shape[1]).to(device)
    opt = torch.optim.Adam(modelo.parameters(), lr=args.lr)
    # Igual que class_weight="balanced" en sklearn: pesa más la clase minoritaria.
    pos_weight = torch.tensor([(1 - y_train.mean()) / max(y_train.mean(), 1e-6)], device=device)
    criterio = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    X_train_t = torch.from_numpy(X_train).float()
    y_train_t = torch.from_numpy(y_train).float()
    n = len(X_train_t)

    t0 = time.perf_counter()
    for epoca in range(args.epocas):
        modelo.train()
        perm = torch.randperm(n)
        perdida_total = 0.0
        for i in range(0, n, args.batch_size):
            idx = perm[i:i + args.batch_size]
            xb = X_train_t[idx].to(device)
            yb = y_train_t[idx].to(device)
            opt.zero_grad()
            logits = modelo(xb)
            perdida = criterio(logits, yb)
            perdida.backward()
            opt.step()
            perdida_total += perdida.item() * len(idx)
        print(f"  época {epoca+1}/{args.epocas}: loss={perdida_total/n:.4f} "
              f"({time.perf_counter()-t0:.1f}s acumulado)", flush=True)

    modelo.eval()
    with torch.no_grad():
        logits_val = modelo(torch.from_numpy(X_val).float().to(device)).cpu().numpy()
    proba_val = 1 / (1 + np.exp(-logits_val))
    pred_val = (proba_val >= 0.5).astype(int)
    acc = accuracy_score(y_val, pred_val)
    auc = roc_auc_score(y_val, proba_val)
    print(f"Validación: accuracy={acc:.4f} auc={auc:.4f}")

    torch.save(modelo.state_dict(), args.out)
    with open(args.out + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "columnas": columnas,
            "media": media.tolist(),
            "desv": desv.tolist(),
            "ocultas": [128, 64],
        }, f, ensure_ascii=False)
    print(f"Modelo guardado en {args.out}")


if __name__ == "__main__":
    main()
