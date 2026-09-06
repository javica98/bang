"""Bot de Deep Learning supervisado — Fase 4 del roadmap de IA.

Igual que MCTSBotAI y LLMBotAI: solo decide "qué carta jugar", puntuando
cada candidata legal con un clasificador entrenado por imitación sobre
partidas heurísticas (ver collect_dataset.py / train_sklearn.py /
train_torch.py / train_xgboost.py), y elige la de mayor probabilidad.
Todo lo demás se delega al BotAI heurístico interno.

Comparación de las 3 librerías (2.5M filas, mismo dataset y split):

    backend      train    tamaño     accuracy   auc
    sklearn (RF) 323.0s   809.48 MB  0.7679     0.8636
    torch (MLP)   28.5s     0.07 MB  0.7810     0.8780
    xgboost       29.8s     1.31 MB  0.7729     0.8743

XGBoost es el punto medio ideal: casi tan preciso como PyTorch, cientos
de veces más pequeño que el RandomForest de sklearn, y mucho más rápido
de entrenar que ambos. LightGBM (no incluido como backend, solo probado
en la comparación) fue aún más pequeño (0.72MB) con precisión parecida.
"""
import json
import os
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bot_ai import BotAI  # noqa: E402
from features import features_estado, fila_completa, nombre_de_opcion  # noqa: E402

MODELO_SKLEARN_DEFECTO = os.path.join(SIM_DIR, "modelo_sklearn.joblib")
MODELO_TORCH_DEFECTO = os.path.join(SIM_DIR, "modelo_torch.pt")
MODELO_XGBOOST_DEFECTO = os.path.join(SIM_DIR, "modelo_xgboost.json")


class DLBotAI:
    def __init__(self, bot_id, backend="sklearn", modelo_path=None):
        self.bot_id = bot_id
        self.backend = backend
        self._heuristico = BotAI(bot_id)
        self._cargar_modelo(modelo_path)
        # Igual que MCTSBotAI/LLMBotAI: si la última acción elegida no
        # cambió la mano (no-op), se descarta esa opción la próxima vez.
        self._ultima_eleccion = None
        self._acciones_fallidas = set()

    def _cargar_modelo(self, modelo_path):
        if self.backend == "sklearn":
            import joblib
            path = modelo_path or MODELO_SKLEARN_DEFECTO
            self._modelo = joblib.load(path)
            # El modelo se entrenó con n_jobs=-1 (útil para el fit en 2.5M
            # filas), pero en inferencia cada decisión solo puntúa un puñado
            # de candidatas: paralelizar eso es puro overhead (arrancar
            # workers cuesta más que la predicción). Forzar n_jobs=1 aquí.
            self._modelo.n_jobs = 1
            with open(path + ".columnas.json", encoding="utf-8") as f:
                self._columnas = json.load(f)
        elif self.backend == "torch":
            import torch
            from train_torch import MLP
            path = modelo_path or MODELO_TORCH_DEFECTO
            with open(path + ".meta.json", encoding="utf-8") as f:
                meta = json.load(f)
            self._columnas = meta["columnas"]
            self._media = np.array(meta["media"], dtype=np.float32)
            self._desv = np.array(meta["desv"], dtype=np.float32)
            self._modelo = MLP(len(self._columnas), tuple(meta["ocultas"]))
            self._modelo.load_state_dict(torch.load(path, map_location="cpu"))
            self._modelo.eval()
            self._torch = torch
        elif self.backend == "xgboost":
            import xgboost as xgb
            path = modelo_path or MODELO_XGBOOST_DEFECTO
            self._modelo = xgb.XGBClassifier()
            self._modelo.load_model(path)
            with open(path + ".columnas.json", encoding="utf-8") as f:
                self._columnas = json.load(f)
        else:
            raise ValueError(f"backend desconocido: {self.backend!r} (usa 'sklearn', 'torch' o 'xgboost')")

    def observar(self, señal, actor_id):
        self._heuristico.observar(señal, actor_id)

    def decidir(self, pregunta, jugador, juego):
        if juego is not None:
            self._heuristico._inicializar(juego)
        if pregunta.get("tipo") == "elegir_carta":
            return self._decidir_carta_dl(pregunta, jugador, juego)
        return self._heuristico.decidir(pregunta, jugador, juego)

    def _decidir_carta_dl(self, pregunta, jugador, juego):
        mano = pregunta.get("mano", [])
        opciones_todas = list(pregunta.get("opciones", []))
        if pregunta.get("permitir_fin", True):
            opciones_todas.append("FIN")
        if pregunta.get("permitir_poder", False):
            opciones_todas.append("PODER")

        if self._ultima_eleccion is not None:
            prev_accion, prev_len = self._ultima_eleccion
            if prev_len == len(mano):
                self._acciones_fallidas.add(prev_accion)
            else:
                self._acciones_fallidas.clear()
            self._ultima_eleccion = None
        else:
            self._acciones_fallidas.clear()

        opciones_validas = [op for op in opciones_todas if op not in self._acciones_fallidas]
        if not opciones_validas:
            opciones_validas = opciones_todas
        if len(opciones_validas) <= 1:
            elegido = opciones_validas[0] if opciones_validas else "FIN"
            self._ultima_eleccion = (elegido, len(mano))
            return elegido

        # Varias opciones pueden ser la misma carta por nombre (dos Bang en
        # mano, p.ej.) — solo hace falta puntuar cada NOMBRE una vez y
        # devolver cualquier opción concreta que lo represente.
        opcion_por_nombre = {}
        for op in opciones_validas:
            nombre = nombre_de_opcion(op, mano)
            if nombre is not None:
                opcion_por_nombre[nombre] = op

        estado_feats = features_estado(pregunta, jugador, juego)
        nombres = list(opcion_por_nombre.keys())
        X = self._construir_lote(estado_feats, nombres)
        scores = self._puntuar_lote(X)
        mejor_nombre = nombres[int(np.argmax(scores))]
        elegido = opcion_por_nombre[mejor_nombre]
        self._ultima_eleccion = (elegido, len(mano))
        return elegido

    def _construir_lote(self, estado_feats, nombres):
        """Una fila de features por candidata, en UNA sola matriz — para
        puntuar todas con una sola llamada al modelo en vez de una por carta."""
        filas = []
        for nombre in nombres:
            fila = fila_completa(estado_feats, nombre, label=0)
            fila.pop("label", None)
            filas.append([fila.get(c, 0.0) for c in self._columnas])
        return np.asarray(filas, dtype=np.float32)

    def _puntuar_lote(self, X):
        if self.backend in ("sklearn", "xgboost"):
            return self._modelo.predict_proba(X)[:, 1]
        Xn = (X - self._media) / self._desv
        with self._torch.no_grad():
            logits = self._modelo(self._torch.from_numpy(Xn).float()).numpy()
        return 1.0 / (1.0 + np.exp(-logits))
