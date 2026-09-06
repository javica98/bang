"""Tests del entorno RL (Fase 5): el entorno responde a reset/step con
observaciones y máscaras del tamaño correcto, y una partida completa con
RLBotAI (envolviendo un modelo recién inicializado, sin entrenar) no
revienta. No entrena de verdad — eso se hace aparte con train_rl.py.
"""
import numpy as np
import pytest

from sim.rl_env import BangCardEnv, oponente_heuristico
from sim.rl_common import N_OBS, N_ACCIONES


def test_reset_y_step_devuelven_formas_correctas():
    env = BangCardEnv(oponente_sampler=oponente_heuristico, max_pasos=1500)
    obs, info = env.reset()
    assert obs.shape == (N_OBS,)
    mask = env.action_masks()
    assert mask.shape == (N_ACCIONES,)
    assert mask.dtype == bool
    assert mask.any(), "siempre debe haber al menos una acción legal (FIN)"

    accion = int(np.where(mask)[0][0])
    obs2, recompensa, terminado, truncado, info = env.step(accion)
    assert obs2.shape == (N_OBS,)
    assert isinstance(terminado, bool)


def test_episodio_completo_con_acciones_validas_aleatorias():
    env = BangCardEnv(oponente_sampler=oponente_heuristico, max_pasos=2000)
    obs, info = env.reset()
    terminado = False
    pasos = 0
    rng = np.random.default_rng(0)
    while not terminado and pasos < 500:
        mask = env.action_masks()
        accion = rng.choice(np.where(mask)[0])
        obs, recompensa, terminado, truncado, info = env.step(accion)
        pasos += 1
    assert terminado
    assert recompensa in (1.0, -1.0)


@pytest.mark.slow
def test_maskable_ppo_entrena_sin_reventar():
    sb3_contrib = pytest.importorskip("sb3_contrib")
    from sb3_contrib.common.wrappers import ActionMasker

    def mask_fn(e):
        return e.action_masks()

    env = ActionMasker(BangCardEnv(oponente_sampler=oponente_heuristico, max_pasos=1500), mask_fn)
    modelo = sb3_contrib.MaskablePPO("MlpPolicy", env, verbose=0, n_steps=64, batch_size=32)
    modelo.learn(total_timesteps=128)
