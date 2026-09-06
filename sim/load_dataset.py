"""Carga una muestra manejable de un dataset en shards (ver collect_dataset.py)
sin tener que cargarlo entero en memoria.
"""
import json
import os
import random

import numpy as np


def cargar_muestra(carpeta, max_filas=None, seed=0):
    """Carga shards completos (en orden aleatorio) hasta acumular ~max_filas
    filas (o todos los shards si max_filas es None). Como cada partida es
    independiente y los shards se llenan en orden de generación, tomar
    shards completos al azar es una muestra representativa razonable sin
    necesidad de barajar fila a fila.
    """
    with open(os.path.join(carpeta, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    columnas = manifest["columnas"]
    shard_paths = [os.path.join(carpeta, f"shard_{i:05d}.npz") for i in range(manifest["n_shards"])]

    rng = random.Random(seed)
    rng.shuffle(shard_paths)

    Xs, ys = [], []
    total = 0
    for path in shard_paths:
        with np.load(path) as data:
            Xs.append(data["X"])
            ys.append(data["y"])
            total += len(data["y"])
        if max_filas is not None and total >= max_filas:
            break

    X = np.concatenate(Xs, axis=0)
    y = np.concatenate(ys, axis=0)
    if max_filas is not None and len(y) > max_filas:
        idx = rng.sample(range(len(y)), max_filas)
        X, y = X[idx], y[idx]
    return X, y, columnas


if __name__ == "__main__":
    import sys
    X, y, columnas = cargar_muestra(sys.argv[1], max_filas=int(sys.argv[2]) if len(sys.argv) > 2 else None)
    print(f"X: {X.shape}, y: {y.shape}, positivos: {y.sum():.0f} ({100*y.mean():.1f}%)")
    print(f"columnas ({len(columnas)}): {columnas[:5]}...")
