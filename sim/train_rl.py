"""Entrenamiento self-play (Fase 5): MaskablePPO contra un pool de
oponentes que empieza solo con la heurística de Fase 1 y va incorporando
snapshots de la propia política a medida que entrena, para que no
colapse memorizando un único estilo de rival fijo.

Uso:
    python sim/train_rl.py --timesteps 300000 --snapshot-cada 25000
"""
import argparse
import os
import random
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SIM_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (BASE_DIR, WEB_DIR, SIM_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sb3_contrib import MaskablePPO  # noqa: E402
from sb3_contrib.common.wrappers import ActionMasker  # noqa: E402
from stable_baselines3.common.callbacks import BaseCallback  # noqa: E402

from bot_ai import BotAI  # noqa: E402
from rl_env import BangCardEnv  # noqa: E402
from rl_bot import RLBotAI  # noqa: E402


class PoolSelfPlay:
    """Mantiene siempre un piso de calidad conocida (heurística, con
    probabilidad `prob_heuristico` en cada muestreo) y, para el resto,
    pesa los snapshots MÁS RECIENTES más que los antiguos (peso lineal
    creciente) — así el entrenamiento se enfrenta sobre todo a versiones
    parecidas a la política actual en vez de a snapshots ya obsoletos,
    evitando además que oponentes muy tempranos (y flojos) sigan pesando
    igual que uno reciente cuando el pool ya tiene decenas de entradas.
    """

    def __init__(self, prob_heuristico=0.15):
        self.snapshots = []  # modelos MaskablePPO cargados, en orden de llegada
        self.prob_heuristico = prob_heuristico

    def añadir_snapshot(self, modelo_path):
        self.snapshots.append(MaskablePPO.load(modelo_path))

    def sampler(self, bot_id):
        if not self.snapshots or random.random() < self.prob_heuristico:
            return BotAI(bot_id)
        pesos = list(range(1, len(self.snapshots) + 1))  # más peso a los últimos
        modelo = random.choices(self.snapshots, weights=pesos, k=1)[0]
        return RLBotAI(bot_id, modelo, deterministico=False)

    @property
    def entradas(self):
        """Solo para logging/inspección — nº de entradas totales del pool."""
        return ["heuristico"] + self.snapshots


class SelfPlayCallback(BaseCallback):
    def __init__(self, pool, cada_pasos, carpeta_checkpoints, verbose=0):
        super().__init__(verbose)
        self.pool = pool
        self.cada_pasos = cada_pasos
        self.carpeta = carpeta_checkpoints
        self._ultimo = 0

    def _on_step(self):
        if self.num_timesteps - self._ultimo >= self.cada_pasos:
            self._ultimo = self.num_timesteps
            path = os.path.join(self.carpeta, f"snapshot_{self.num_timesteps}.zip")
            self.model.save(path)
            self.pool.añadir_snapshot(path)
            if self.verbose:
                print(f"[self-play] snapshot en paso {self.num_timesteps} -> "
                      f"pool={len(self.pool.entradas)} entradas", flush=True)
        return True


def mask_fn(env):
    return env.action_masks()


def main():
    parser = argparse.ArgumentParser(description="Entrenamiento self-play MaskablePPO (Fase 5)")
    parser.add_argument("--timesteps", type=int, default=200_000)
    parser.add_argument("--snapshot-cada", type=int, default=20_000)
    parser.add_argument("--n-steps", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--out", default=os.path.join(SIM_DIR, "modelo_rl_final.zip"))
    parser.add_argument("--checkpoints", default=os.path.join(SIM_DIR, "rl_checkpoints"))
    parser.add_argument("--logdir", default=os.path.join(SIM_DIR, "rl_tensorboard"))
    parser.add_argument("--max-pasos-partida", type=int, default=3000)
    parser.add_argument("--prob-heuristico", type=float, default=0.15)
    parser.add_argument("--modelo-inicial", default=None,
                         help="Ruta a un modelo pre-entrenado (pretrain_rl.py) para arrancar en "
                              "caliente en vez de pesos aleatorios.")
    parser.add_argument("--net-arch", type=int, nargs="+", default=[256, 256],
                         help="Capas ocultas de la red (por defecto SB3 usa [64, 64]).")
    parser.add_argument("--solo-carta", action="store_true",
                         help="Vuelve al alcance original (solo 'qué carta jugar'); a quién apuntar "
                              "y si esquivar los resuelve la heurística. Sirve para aislar el efecto "
                              "de red/arranque en caliente/shaping/pool de la ampliación de alcance.")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    os.makedirs(args.checkpoints, exist_ok=True)

    pool = PoolSelfPlay(prob_heuristico=args.prob_heuristico)
    env = BangCardEnv(oponente_sampler=pool.sampler, max_pasos=args.max_pasos_partida,
                       alcance_completo=not args.solo_carta)
    env = ActionMasker(env, mask_fn)

    if args.modelo_inicial:
        print(f"Arrancando desde el modelo pre-entrenado: {args.modelo_inicial}")
        modelo = MaskablePPO.load(
            args.modelo_inicial, env=env, verbose=1, tensorboard_log=args.logdir,
            n_steps=args.n_steps, batch_size=args.batch_size,
        )
    else:
        modelo = MaskablePPO(
            "MlpPolicy", env, verbose=1, tensorboard_log=args.logdir,
            n_steps=args.n_steps, batch_size=args.batch_size,
            policy_kwargs=dict(net_arch=list(args.net_arch)),
        )
    callback = SelfPlayCallback(pool, args.snapshot_cada, args.checkpoints, verbose=1)
    modelo.learn(total_timesteps=args.timesteps, callback=callback)
    modelo.save(args.out)
    print(f"\nModelo final guardado en {args.out} (pool final: {len(pool.entradas)} entradas)")


if __name__ == "__main__":
    main()
