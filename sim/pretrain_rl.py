"""Pre-entrena la política de MaskablePPO por imitación (behavior cloning)
sobre partidas heurísticas — un "arranque en caliente" antes de empezar el
self-play real (Fase 5). No se puede cargar directamente el modelo de
Fase 4 porque tiene una arquitectura distinta (puntúa una candidata a la
vez; aquí la política decide sobre las 24 acciones de golpe), así que se
re-imita la misma heurística pero en el formato nativo del entorno RL.

Uso:
    python sim/collect_rl_pretrain_data.py -n 5000 -o rl_pretrain_data.npz
    python sim/pretrain_rl.py --datos rl_pretrain_data.npz --out modelo_rl_preentrenado.zip
"""
import argparse
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sb3_contrib import MaskablePPO  # noqa: E402
from sb3_contrib.common.wrappers import ActionMasker  # noqa: E402
from rl_env import BangCardEnv, oponente_heuristico  # noqa: E402


def mask_fn(env):
    return env.action_masks()


def main():
    parser = argparse.ArgumentParser(description="Pre-entrena la política PPO por imitación (Fase 5)")
    parser.add_argument("--datos", required=True)
    parser.add_argument("--epocas", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-frac", type=float, default=0.1)
    parser.add_argument("--out", default=os.path.join(SIM_DIR, "modelo_rl_preentrenado.zip"))
    parser.add_argument("--net-arch", type=int, nargs="+", default=[256, 256],
                         help="Debe coincidir con el --net-arch que se use luego en train_rl.py.")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    datos = np.load(args.datos)
    obs, acciones, mascaras = datos["obs"], datos["acciones"], datos["mascaras"]
    n = len(acciones)
    n_val = int(n * args.val_frac)
    idx = np.random.permutation(n)
    idx_val, idx_train = idx[:n_val], idx[n_val:]
    print(f"Datos: {n} decisiones ({len(idx_train)} train / {len(idx_val)} val)")

    # Un entorno real solo para que MaskablePPO construya la política con
    # los espacios de observación/acción correctos (no se usa para jugar).
    env = BangCardEnv(oponente_sampler=oponente_heuristico, max_pasos=1500)
    env = ActionMasker(env, mask_fn)
    modelo = MaskablePPO("MlpPolicy", env, policy_kwargs=dict(net_arch=list(args.net_arch)))
    policy = modelo.policy
    optimizer = torch.optim.Adam(policy.parameters(), lr=args.lr)

    obs_t = torch.as_tensor(obs, dtype=torch.float32)
    acc_t = torch.as_tensor(acciones, dtype=torch.long)
    mask_t = torch.as_tensor(mascaras, dtype=torch.bool)

    def evaluar(indices):
        policy.eval()
        with torch.no_grad():
            ob, ac, mk = obs_t[indices], acc_t[indices], mask_t[indices]
            features = policy.extract_features(ob)
            latent_pi, _ = policy.mlp_extractor(features)
            logits = policy.action_net(latent_pi).masked_fill(~mk, -1e8)
            perdida = F.cross_entropy(logits, ac).item()
            acc = (logits.argmax(dim=1) == ac).float().mean().item()
        policy.train()
        return perdida, acc

    for epoca in range(args.epocas):
        perm = np.random.permutation(idx_train)
        perdida_total, n_vistos = 0.0, 0
        for i in range(0, len(perm), args.batch_size):
            lote = perm[i:i + args.batch_size]
            ob, ac, mk = obs_t[lote], acc_t[lote], mask_t[lote]
            features = policy.extract_features(ob)
            latent_pi, _ = policy.mlp_extractor(features)
            logits = policy.action_net(latent_pi).masked_fill(~mk, -1e8)
            perdida = F.cross_entropy(logits, ac)
            optimizer.zero_grad()
            perdida.backward()
            optimizer.step()
            perdida_total += perdida.item() * len(lote)
            n_vistos += len(lote)

        perdida_val, acc_val = evaluar(idx_val)
        print(f"época {epoca+1}/{args.epocas}: loss_train={perdida_total/n_vistos:.4f} "
              f"loss_val={perdida_val:.4f} acc_val={acc_val:.4f}", flush=True)

    modelo.save(args.out)
    print(f"\nModelo pre-entrenado guardado en {args.out}")


if __name__ == "__main__":
    main()
