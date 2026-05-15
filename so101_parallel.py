# ============================================================
# Genesis SO-101アーム - 5並列強化学習（PPO）Mac対応版
#
# ★ ビューワーの仕組み（元のテレオペから学んだこと）:
#   Macでは viewer.start() は不要・むしろNG。
#   scene.step() を while ループで呼び続けるだけでビューワーが更新される。
#   → 学習ループも「while で scene.step() を回す」形にすれば表示される。
#
# ★ 並列化:
#   scene.build(n_envs=5, env_spacing=(0.7, 0.7)) で
#   1シーンに5体を0.7m間隔でグリッド配置。
#
# 実行:
#   python so101_parallel.py --mode train          # 5並列学習 + ビューワー
#   python so101_parallel.py --mode train --no_viewer  # ビューワーなし高速
#   python so101_parallel.py --mode demo           # 学習済みデモ
#   python so101_parallel.py                       # キーボードテレオペ（元のまま）
# ============================================================

import genesis as gs
import numpy as np
import torch
import torch.nn as nn
import os
import re
import urllib.request
import matplotlib
matplotlib.use("Agg")
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecEnv, VecMonitor, DummyVecEnv
from stable_baselines3.common.callbacks import (
    CheckpointCallback, EvalCallback, BaseCallback
)
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from gymnasium import spaces

# ============================================================
# STEP 1: URDF ダウンロード
# ============================================================
URDF_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "so101_urdf")
URDF_PATH = os.path.join(URDF_DIR, "so101.urdf")

def download_so101():
    os.makedirs(URDF_DIR, exist_ok=True)
    os.makedirs(os.path.join(URDF_DIR, "assets"), exist_ok=True)
    urdf_url = "https://huggingface.co/haixuantao/dora-bambot/resolve/main/URDF/so101.urdf"
    print("SO-101 URDFをダウンロード中...")
    urllib.request.urlretrieve(urdf_url, URDF_PATH)
    print("✓ URDF ダウンロード完了")
    with open(URDF_PATH, "r") as f:
        content = f.read()
    stl_files = set(
        os.path.basename(m)
        for m in re.findall(r'filename="([^"]+\.stl)"', content, re.IGNORECASE)
    )
    base_url = "https://huggingface.co/haixuantao/dora-bambot/resolve/main/URDF/assets/"
    for stl in stl_files:
        dest = os.path.join(URDF_DIR, "assets", stl)
        if not os.path.exists(dest):
            try:
                urllib.request.urlretrieve(base_url + stl, dest)
                print(f"  ✓ {stl}")
            except Exception as e:
                print(f"  ✗ {stl}: {e}")

if not os.path.exists(URDF_PATH):
    download_so101()
else:
    print("✓ URDFはすでに存在します")


# ============================================================
# STEP 2: カスタムネットワーク
# ============================================================
class CustomMLP(BaseFeaturesExtractor):
    def __init__(self, observation_space: spaces.Box, features_dim: int = 256):
        super().__init__(observation_space, features_dim)
        n_input = observation_space.shape[0]
        self.net = nn.Sequential(
            nn.Linear(n_input, 256), nn.Tanh(),
            nn.Linear(256, 256),     nn.Tanh(),
            nn.Linear(256, features_dim), nn.Tanh(),
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)


# ============================================================
# STEP 3: Genesis ネイティブ並列 VecEnv
#
# ★ ポイント: SB3の model.learn() は内部で step_async/step_wait を
#   呼ぶだけなので、scene.step() は step_wait() の中で1回呼ぶだけでよい。
#   ビューワーは scene.step() のたびに自動更新される（viewer.start()不要）。
# ============================================================
class GenesisParallelVecEnv(VecEnv):

    N_CUBES          = 5
    MAX_STEPS        = 500
    CUBE_LIFT_HEIGHT = 0.07
    ACTION_SCALE     = 0.05
    DT               = 0.01
    CUBE_X_MIN, CUBE_X_MAX = 0.05, 0.18
    CUBE_Y_MIN, CUBE_Y_MAX = -0.25, -0.02

    def __init__(self, n_envs: int = 5, show_viewer: bool = True, backend=None):
        self.n_envs_parallel = n_envs
        self.show_viewer     = show_viewer
        self._step_counts    = np.zeros(n_envs, dtype=np.int32)
        self._rng            = np.random.default_rng()

        try:
            _backend = backend if backend is not None else gs.cpu
            gs.init(backend=_backend, logging_level="warning")
        except Exception:
            pass

        self._build_scene()

        n       = self.n_dofs
        obs_dim = 2 * n + 3 + self.N_CUBES * 3 + self.N_CUBES + 1
        observation_space = spaces.Box(-np.inf, np.inf, shape=(obs_dim,), dtype=np.float32)
        action_space      = spaces.Box(-1.0, 1.0, shape=(n,), dtype=np.float32)
        super().__init__(n_envs, observation_space, action_space)

    @staticmethod
    def _calc_camera(n: int, spacing: float):
        """
        n_envs と env_spacing から最適なカメラパラメータを自動計算。

        Genesisは n_envs 個の環境を ceil(sqrt(n)) × ceil(sqrt(n)) のグリッドに配置する。
        グリッド全体の中心を lookat にし、全体が収まるよう距離・高さ・FOVを決める。

        Returns: camera_pos, camera_lookat, camera_fov
        """
        import math
        cols = math.ceil(math.sqrt(n))          # グリッド列数
        rows = math.ceil(n / cols)              # グリッド行数

        # グリッド全体の中心（X方向・Y方向）
        cx = (cols - 1) * spacing / 2.0
        cy = (rows - 1) * spacing / 2.0

        # カバーすべき半径（対角の半分）
        half_diag = math.sqrt(cx**2 + cy**2) + spacing * 0.5

        # カメラを斜め後方に置く: 距離はhalf_diagに比例
        dist      = half_diag * 2.8
        height    = half_diag * 2.0
        cam_pos   = (cx + dist * 0.6, cy - dist, height)
        cam_lookat = (cx, cy, 0.1)

        # FOVはグリッドサイズに応じて広げる（最大75°）
        fov = min(75, 40 + cols * 5)

        return cam_pos, cam_lookat, fov

    def _build_scene(self):
        # env_spacingとカメラを台数に応じて自動決定
        spacing = 0.7
        cam_pos, cam_lookat, cam_fov = self._calc_camera(self.n_envs_parallel, spacing)

        scene_kwargs = dict(
            sim_options=gs.options.SimOptions(dt=self.DT, substeps=5),
            show_viewer=self.show_viewer,
            show_FPS=self.show_viewer,
        )
        if self.show_viewer:
            print(f"   カメラ自動設定: pos={tuple(round(v,2) for v in cam_pos)}, "
                  f"lookat={tuple(round(v,2) for v in cam_lookat)}, fov={cam_fov}°")
            scene_kwargs["viewer_options"] = gs.options.ViewerOptions(
                camera_pos=cam_pos,
                camera_lookat=cam_lookat,
                camera_fov=cam_fov,
                max_FPS=60,
            )

        self.scene = gs.Scene(**scene_kwargs)
        self.scene.add_entity(gs.morphs.Plane())

        try:
            self.robot = self.scene.add_entity(
                gs.morphs.URDF(file=URDF_PATH, pos=(0, 0, 0), fixed=True)
            )
        except Exception as e:
            print(f"URDF読み込みエラー ({e})、Pandaで代替")
            self.robot = self.scene.add_entity(
                gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml")
            )

        default_positions = [
            (0.12, -0.08, 0.02), (0.12,  0.08, 0.02),
            (0.16,  0.00, 0.02), (0.18, -0.08, 0.02),
            (0.18,  0.08, 0.02),
        ]
        self.cubes = [
            self.scene.add_entity(
                gs.morphs.Box(size=(0.04, 0.04, 0.04), pos=p, fixed=False)
            )
            for p in default_positions
        ]

        # env_spacing で各環境を視覚的にグリッド配置
        self.scene.build(
            n_envs=self.n_envs_parallel,
            env_spacing=(spacing, spacing),
        )
        self.n_dofs = self.robot.n_dofs
        print(f"✓ Genesis 並列シーン構築完了 "
              f"(n_envs={self.n_envs_parallel}, DoF={self.n_dofs}, "
              f"viewer={'ON' if self.show_viewer else 'OFF'})")

    def _get_obs_batch(self) -> np.ndarray:
        qpos_all = self.robot.get_dofs_position().cpu().numpy()
        qvel_all = self.robot.get_dofs_velocity().cpu().numpy()
        try:
            eef_all = self.robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            eef_all = np.tile([0.10, -0.15, 0.28], (self.n_envs_parallel, 1)).astype(np.float32)

        obs_list = []
        for i in range(self.n_envs_parallel):
            eef_pos   = eef_all[i]
            cube_poss = np.stack([c.get_pos().cpu().numpy()[i] for c in self.cubes])
            dists     = np.linalg.norm(cube_poss - eef_pos, axis=1)
            nearest   = np.array([float(np.argmin(dists))])
            obs_list.append(
                np.concatenate([qpos_all[i], qvel_all[i], eef_pos,
                                cube_poss.flatten(), dists, nearest]).astype(np.float32)
            )
        return np.stack(obs_list)

    def _compute_rewards_batch(self):
        try:
            eef_all = self.robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            eef_all = np.tile([0.10, -0.15, 0.28], (self.n_envs_parallel, 1)).astype(np.float32)

        rewards   = np.zeros(self.n_envs_parallel, dtype=np.float32)
        successes = np.zeros(self.n_envs_parallel, dtype=bool)
        for i in range(self.n_envs_parallel):
            cube_poss    = np.stack([c.get_pos().cpu().numpy()[i] for c in self.cubes])
            dists        = np.linalg.norm(cube_poss - eef_all[i], axis=1)
            nearest_idx  = int(np.argmin(dists))
            nearest_z    = float(cube_poss[nearest_idx, 2])
            success      = nearest_z > self.CUBE_LIFT_HEIGHT
            rewards[i]   = (-dists[nearest_idx] * 1.5
                            + max(0.0, nearest_z - 0.02) * 8.0
                            + (30.0 if success else 0.0) - 0.01)
            successes[i] = success
        return rewards, successes

    def reset(self) -> np.ndarray:
        self._step_counts[:] = 0
        zero_q = np.zeros((self.n_envs_parallel, self.n_dofs), dtype=np.float32)
        self.robot.set_dofs_position(zero_q)
        self.robot.set_dofs_velocity(zero_q)
        for cube in self.cubes:
            positions = np.stack([
                [self._rng.uniform(self.CUBE_X_MIN, self.CUBE_X_MAX),
                 self._rng.uniform(self.CUBE_Y_MIN, self.CUBE_Y_MAX), 0.02]
                for _ in range(self.n_envs_parallel)
            ]).astype(np.float32)
            cube.set_pos(positions)
            cube.set_quat(
                np.tile([1., 0., 0., 0.], (self.n_envs_parallel, 1)).astype(np.float32)
            )
        for _ in range(10):
            self.scene.step()
        return self._get_obs_batch()

    def step_async(self, actions: np.ndarray) -> None:
        self._pending_actions = actions

    def step_wait(self):
        self._step_counts += 1
        current_qpos = self.robot.get_dofs_position().cpu().numpy()
        delta        = np.clip(self._pending_actions, -1.0, 1.0) * self.ACTION_SCALE
        target_qpos  = np.clip(current_qpos + delta, -np.pi, np.pi).astype(np.float32)
        self.robot.set_dofs_position(target_qpos)

        # ★ ここで scene.step() → ビューワーが自動更新される（viewer.start()不要）
        self.scene.step()

        obs_batch          = self._get_obs_batch()
        rewards, successes = self._compute_rewards_batch()
        dones              = successes | (self._step_counts >= self.MAX_STEPS)

        # 終了した環境だけ個別リセット
        for env_i in np.where(dones)[0]:
            self._step_counts[env_i] = 0
            self.robot.set_dofs_position(
                np.zeros(self.n_dofs, dtype=np.float32), envs_idx=[env_i])
            self.robot.set_dofs_velocity(
                np.zeros(self.n_dofs, dtype=np.float32), envs_idx=[env_i])
            for cube in self.cubes:
                cube.set_pos(
                    np.array([[self._rng.uniform(self.CUBE_X_MIN, self.CUBE_X_MAX),
                               self._rng.uniform(self.CUBE_Y_MIN, self.CUBE_Y_MAX),
                               0.02]], dtype=np.float32),
                    envs_idx=[env_i])
                cube.set_quat(
                    np.array([[1., 0., 0., 0.]], dtype=np.float32),
                    envs_idx=[env_i])

        infos = [{"success": bool(successes[i])} for i in range(self.n_envs_parallel)]
        return obs_batch, rewards, dones, infos

    def close(self): pass
    def env_is_wrapped(self, wrapper_class, indices=None): return [False] * self.n_envs
    def env_method(self, method_name, *args, indices=None, **kwargs): return []
    def get_attr(self, attr_name, indices=None): return [None] * self.n_envs
    def set_attr(self, attr_name, value, indices=None): pass
    def seed(self, seed=None): return [None] * self.n_envs
    def render(self, mode="human"): pass


# ============================================================
# STEP 4: 学習
# ============================================================
def train(n_parallel: int = 5, show_viewer: bool = True, backend=None):
    SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genesis_so101_rl")
    LOG_DIR  = os.path.join(SAVE_DIR, "logs")
    os.makedirs(SAVE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR,  exist_ok=True)

    backend_name = {None: "CPU", "metal": "Metal(Apple Silicon)", "cuda": "CUDA"}.get(
        str(backend) if backend else None, str(backend)
    )
    print(f"\n🚀 Genesis ネイティブ並列: {n_parallel} 環境同時実行")
    print(f"   バックエンド: {backend_name}")
    print(f"   ビューワー: {'ON' if show_viewer else 'OFF（高速モード）'}\n")

    train_env = GenesisParallelVecEnv(n_envs=n_parallel, show_viewer=show_viewer, backend=backend)
    train_env = VecMonitor(train_env, LOG_DIR)

    policy_kwargs = dict(
        features_extractor_class=CustomMLP,
        features_extractor_kwargs=dict(features_dim=256),
        net_arch=dict(pi=[256, 128], vf=[256, 128]),
        activation_fn=nn.Tanh,
    )

    model = PPO(
        policy="MlpPolicy", env=train_env,
        learning_rate=lambda p: 3e-4 * p,
        n_steps=2048, batch_size=256, n_epochs=10,
        gamma=0.99, gae_lambda=0.95, clip_range=0.2,
        ent_coef=0.005, vf_coef=0.5, max_grad_norm=0.5,
        policy_kwargs=policy_kwargs,
        tensorboard_log=LOG_DIR, verbose=1, device="cpu",
    )

    checkpoint_path = os.path.join(SAVE_DIR, "best_model.zip")
    if os.path.exists(checkpoint_path):
        try:
            model = PPO.load(checkpoint_path, env=train_env, device="cpu")
            print(f"✓ チェックポイントをロード: {checkpoint_path}")
        except ValueError as e:
            print(f"⚠️ 観測空間不一致のため新規学習: {e}")
            import shutil
            shutil.move(checkpoint_path, checkpoint_path.replace(".zip", "_old.zip"))

    checkpoint_cb = CheckpointCallback(
        save_freq=10_000, save_path=SAVE_DIR, name_prefix="ppo_so101"
    )
    eval_env = GenesisParallelVecEnv(n_envs=1, show_viewer=False, backend=backend)
    eval_env = VecMonitor(eval_env)
    eval_cb  = EvalCallback(
        eval_env, best_model_save_path=SAVE_DIR, log_path=LOG_DIR,
        eval_freq=20_000, n_eval_episodes=5, deterministic=True, render=False,
    )

    TOTAL_TIMESTEPS = 300_000
    print(f"学習開始: {TOTAL_TIMESTEPS:,} ステップ\n")

    # ★ viewer.start() は呼ばない。
    #   model.learn() の内部で step_wait() → scene.step() が回り続けるので
    #   ビューワーは自動的に更新される（元のテレオペと同じ仕組み）。
    model.learn(
        total_timesteps=TOTAL_TIMESTEPS,
        callback=[checkpoint_cb, eval_cb],
        tb_log_name="ppo_so101_parallel",
        reset_num_timesteps=False,
    )

    final_path = os.path.join(SAVE_DIR, "ppo_so101_final")
    model.save(final_path)
    print(f"\n✓ 学習完了! モデル保存: {final_path}.zip")

    train_env.close()
    eval_env.close()
    return model, SAVE_DIR


# ============================================================
# STEP 5: デモ再生（元のSO101ViewerEnvと同仕様）
# ============================================================
class SO101ViewerEnv:
    N_CUBES          = 5
    CUBE_LIFT_HEIGHT = 0.07
    ACTION_SCALE     = 0.05
    DT               = 0.01
    CUBE_X_MIN, CUBE_X_MAX = 0.05, 0.18
    CUBE_Y_MIN, CUBE_Y_MAX = -0.25, -0.02

    def __init__(self):
        try:
            gs.init(backend=gs.cpu, logging_level="info")
        except Exception:
            pass
        self.scene = gs.Scene(
            sim_options=gs.options.SimOptions(dt=self.DT, substeps=5),
            viewer_options=gs.options.ViewerOptions(
                camera_pos=(0.8, -0.8, 0.6),
                camera_lookat=(0.15, 0., 0.1),
                camera_fov=50, max_FPS=60,
            ),
            show_viewer=True, show_FPS=True,
        )
        self.scene.add_entity(gs.morphs.Plane())
        try:
            self.robot = self.scene.add_entity(
                gs.morphs.URDF(file=URDF_PATH, pos=(0, 0, 0), fixed=True)
            )
        except Exception as e:
            print(f"URDF読み込みエラー ({e})、Pandaで代替")
            self.robot = self.scene.add_entity(
                gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml")
            )
        colors = [(1.,0.3,0.3),(0.3,1.,0.3),(0.3,0.3,1.),(1.,1.,0.3),(1.,0.5,0.)]
        self.cubes = [
            self.scene.add_entity(
                material=gs.materials.Rigid(rho=300),
                morph=gs.morphs.Box(size=(0.04,0.04,0.04), pos=p, fixed=False),
                surface=gs.surfaces.Default(color=(*c, 1.)),
            )
            for p, c in zip(
                [(0.12,-0.08,0.02),(0.12,0.08,0.02),(0.16,0.,0.02),
                 (0.18,-0.08,0.02),(0.18,0.08,0.02)],
                colors,
            )
        ]
        self.scene.build()
        self.n_dofs = self.robot.n_dofs

    def _get_eef_pos(self):
        try:
            return self.robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            return np.array([0.10, -0.15, 0.28], dtype=np.float32)

    def _get_obs(self):
        qpos = self.robot.get_dofs_position().cpu().numpy()
        qvel = self.robot.get_dofs_velocity().cpu().numpy()
        eef  = self._get_eef_pos()
        cube_poss = np.stack([c.get_pos().cpu().numpy() for c in self.cubes])
        dists     = np.linalg.norm(cube_poss - eef, axis=1)
        nearest   = np.array([float(np.argmin(dists))])
        return np.concatenate([qpos, qvel, eef, cube_poss.flatten(), dists, nearest]).astype(np.float32)

    def reset(self, seed=None):
        rng = np.random.default_rng(seed)
        self.robot.set_dofs_position(np.zeros(self.n_dofs, dtype=np.float32))
        self.robot.set_dofs_velocity(np.zeros(self.n_dofs, dtype=np.float32))
        for cube in self.cubes:
            cube.set_pos(np.array([rng.uniform(self.CUBE_X_MIN, self.CUBE_X_MAX),
                                   rng.uniform(self.CUBE_Y_MIN, self.CUBE_Y_MAX),
                                   0.02], dtype=np.float32))
            cube.set_quat(np.array([1.,0.,0.,0.], dtype=np.float32))
        for _ in range(10):
            self.scene.step()
        return self._get_obs()

    def step(self, action):
        qpos   = self.robot.get_dofs_position().cpu().numpy()
        target = np.clip(qpos + np.clip(action,-1.,1.) * self.ACTION_SCALE, -np.pi, np.pi)
        self.robot.set_dofs_position(target.astype(np.float32))
        self.scene.step()   # ← ビューワー自動更新
        obs  = self._get_obs()
        maxZ = float(np.stack([c.get_pos().cpu().numpy() for c in self.cubes])[:,2].max())
        return obs, maxZ > self.CUBE_LIFT_HEIGHT


def run_viewer_demo(model, n_episodes: int = 5):
    """元と同じ: scene.step() を while で回すだけ、viewer.start()なし"""
    print("\n--- ビューワーでリアルタイムデモ開始 ---")
    env = SO101ViewerEnv()
    for ep in range(n_episodes):
        obs, done, step = env.reset(seed=ep), False, 0
        print(f"Episode {ep+1}/{n_episodes} 開始...")
        while not done and step < 500:
            action, _ = model.predict(obs, deterministic=True)
            obs, success = env.step(action)
            step += 1
            if success:
                print(f"  ✓ SUCCESS! ({step}ステップ)")
                done = True
        if not done:
            print(f"  Episode {ep+1}: {step}ステップ完了 (タイムアウト)")
    print("\n✓ デモ終了")


# ============================================================
# STEP 6: キーボードテレオペ（元のコードをそのまま流用）
# ============================================================
def run_keyboard_teleop():
    """元のコードと完全に同じ構造: while scene.step() ループ"""
    from genesis.vis.keybindings import Key, KeyAction, Keybind
    import cv2

    try:
        gs.init(backend=gs.cpu, logging_level="info")
    except Exception:
        pass

    scene = gs.Scene(
        sim_options=gs.options.SimOptions(dt=0.01, substeps=5),
        rigid_options=gs.options.RigidOptions(
            enable_joint_limit=True,
            enable_collision=True,
            gravity=(0, 0, -9.8),
        ),
        viewer_options=gs.options.ViewerOptions(
            camera_pos=(0.8, -0.8, 0.6),
            camera_lookat=(0.15, 0.0, 0.1),
            camera_fov=50,
            max_FPS=60,
        ),
        show_viewer=True,
        show_FPS=True,
    )
    scene.add_entity(gs.morphs.Plane())

    try:
        robot = scene.add_entity(
            material=gs.materials.Rigid(friction=2.0, coup_friction=2.0),
            morph=gs.morphs.URDF(file=URDF_PATH, pos=(0, 0, 0), fixed=True),
        )
        print("✓ SO-101 URDFをロード")
    except Exception as e:
        print(f"URDF読み込みエラー ({e})、Pandaで代替")
        robot = scene.add_entity(gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml"))

    colors = [(1.,0.3,0.3),(0.3,1.,0.3),(0.3,0.3,1.),(1.,1.,0.3),(1.,0.5,0.)]
    cubes  = [
        scene.add_entity(
            material=gs.materials.Rigid(rho=2000, friction=2.0,
                                        coup_friction=2.0, coup_restitution=0.3),
            morph=gs.morphs.Box(size=(0.025,0.025,0.025), pos=p, fixed=False),
            surface=gs.surfaces.Default(color=(*c, 1.0)),
        )
        for p, c in zip(
            [(0.12,-0.08,0.0125),(0.12,0.08,0.0125),(0.16,0.,0.0125),
             (0.18,-0.08,0.0125),(0.18,0.08,0.0125)],
            colors,
        )
    ]

    CAM_W, CAM_H = 400, 300
    cam_overhead = scene.add_camera(
        res=(CAM_W, CAM_H), pos=(0.15, 0., 1.2),
        lookat=(0.15, 0., 0.), fov=55,
    )
    cam_wrist = scene.add_camera(
        res=(CAM_W, CAM_H), pos=(0.15, 0., 0.4),
        lookat=(0.15, 0., 0.), fov=60,
    )

    scene.build()
    n_dofs = robot.n_dofs

    def get_eef_pos():
        try:
            return robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            return np.array([0.15, 0., 0.25], dtype=np.float32)

    def update_wrist_camera():
        eef = get_eef_pos()
        try:
            cam_wrist.set_pose(pos=eef + [0., 0., 0.12], lookat=eef + [0., 0., -0.08])
        except Exception:
            pass

    def grab_frame(cam):
        try:
            frame = cam.render(rgb=True)
            if isinstance(frame, (list, tuple)): frame = frame[0]
            if hasattr(frame, "cpu"): frame = frame.cpu().numpy()
            return frame.astype(np.uint8)
        except Exception:
            return np.zeros((CAM_H, CAM_W, 3), dtype=np.uint8)

    MAIN_WIN_W = 1000
    cv2.namedWindow("overhead", cv2.WINDOW_NORMAL)
    cv2.namedWindow("wrist",    cv2.WINDOW_NORMAL)
    cv2.resizeWindow("overhead", CAM_W, CAM_H)
    cv2.resizeWindow("wrist",    CAM_W, CAM_H)
    cv2.moveWindow("overhead", MAIN_WIN_W + 20, 50)
    cv2.moveWindow("wrist",    MAIN_WIN_W + 20, 50 + CAM_H + 40)

    target_qpos = robot.get_dofs_position().cpu().numpy().astype(np.float32)
    KP, KD, dq  = 200.0, 20.0, 0.03

    def move_joint(idx, delta):
        pos = robot.get_dofs_position().cpu().numpy().astype(np.float32)
        target_qpos[idx] = float(np.clip(pos[idx] + delta, -np.pi, np.pi))

    def apply_pd_control():
        pos = robot.get_dofs_position().cpu().numpy().astype(np.float32)
        vel = robot.get_dofs_velocity().cpu().numpy().astype(np.float32)
        robot.control_dofs_force(KP * (target_qpos - pos) - KD * vel)

    def reset_scene():
        target_qpos[:] = 0.
        robot.set_dofs_position(target_qpos)
        rng = np.random.default_rng()
        for cube in cubes:
            cube.set_pos(np.array([rng.uniform(0.05,0.18), rng.uniform(-0.25,-0.02), 0.0125], dtype=np.float32))
            cube.set_quat(np.array([1.,0.,0.,0.], dtype=np.float32))
        print("↺ リセット完了")

    is_running = True
    def stop(): nonlocal is_running; is_running = False
    def dof(i): return min(i, n_dofs - 1)

    scene.viewer.register_keybinds(
        Keybind("j0+", Key.F1,    KeyAction.HOLD,  callback=move_joint, args=(dof(0),  dq)),
        Keybind("j0-", Key.F2,    KeyAction.HOLD,  callback=move_joint, args=(dof(0), -dq)),
        Keybind("j1+", Key.F3,    KeyAction.HOLD,  callback=move_joint, args=(dof(1),  dq)),
        Keybind("j1-", Key.F4,    KeyAction.HOLD,  callback=move_joint, args=(dof(1), -dq)),
        Keybind("j2+", Key.F5,    KeyAction.HOLD,  callback=move_joint, args=(dof(2),  dq)),
        Keybind("j2-", Key.F6,    KeyAction.HOLD,  callback=move_joint, args=(dof(2), -dq)),
        Keybind("j3+", Key.F7,    KeyAction.HOLD,  callback=move_joint, args=(dof(3),  dq)),
        Keybind("j3-", Key.F8,    KeyAction.HOLD,  callback=move_joint, args=(dof(3), -dq)),
        Keybind("j4+", Key.F9,    KeyAction.HOLD,  callback=move_joint, args=(dof(4),  dq)),
        Keybind("j4-", Key.F10,   KeyAction.HOLD,  callback=move_joint, args=(dof(4), -dq)),
        Keybind("j5+", Key.MINUS, KeyAction.HOLD,  callback=move_joint, args=(dof(5),  dq)),
        Keybind("j5-", Key.EQUAL, KeyAction.HOLD,  callback=move_joint, args=(dof(5), -dq)),
        Keybind("rst", Key.U,     KeyAction.PRESS, callback=reset_scene),
        Keybind("quit",Key.ESCAPE,KeyAction.PRESS, callback=stop),
    )

    CAM_INTERVAL = 5
    step_count   = 0

    # ★ 元と完全に同じ: viewer.start()なし、while scene.step() で回すだけ
    try:
        while is_running:
            apply_pd_control()
            scene.step()

            step_count += 1
            if step_count % CAM_INTERVAL == 0:
                update_wrist_camera()
                img_overhead = grab_frame(cam_overhead)
                img_wrist    = grab_frame(cam_wrist)

                def draw_label(img, text):
                    cv2.rectangle(img, (0,0), (len(text)*11+10, 28), (0,0,0), -1)
                    cv2.putText(img, text, (6,20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,230,255), 1)
                    return img

                draw_label(img_overhead, "OVERHEAD")
                draw_label(img_wrist,    "WRIST")
                cv2.imshow("overhead", cv2.cvtColor(img_overhead, cv2.COLOR_RGB2BGR))
                cv2.imshow("wrist",    cv2.cvtColor(img_wrist,    cv2.COLOR_RGB2BGR))
                cv2.waitKey(1)

    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        print("✓ キーボード操作モード終了")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SO-101 並列RL（Genesis ネイティブ並列）",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode", choices=["train", "demo", "traindemo", "teleop"], default=None,
        help=(
            "（省略）   : キーボードテレオペ\n"
            "train     : 5並列学習（ビューワーON）\n"
            "demo      : 既存モデルでビューワーデモ\n"
            "traindemo : 学習後にビューワーデモ\n"
            "teleop    : キーボードテレオペ"
        ),
    )
    parser.add_argument("--n_envs",    type=int, default=5, help="並列環境数（デフォルト: 5）")
    parser.add_argument("--no_viewer", action="store_true", help="ビューワーを無効化（高速モード）")
    parser.add_argument("--backend",   default="cpu",
                        choices=["cpu", "metal", "cuda", "gpu"],
                        help="Genesisバックエンド (cpu / metal / cuda / gpu, デフォルト: cpu)\n"
                             "Apple Silicon Mac では metal が高速")
    parser.add_argument("--model_path",default=None,        help="demoモード時のモデルパス")
    parser.add_argument("--episodes",  type=int, default=5, help="デモエピソード数")
    args = parser.parse_args()

    SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genesis_so101_rl")

    if args.mode is None or args.mode == "teleop":
        print("=" * 55)
        print(" SO-101 キーボード操作モード（環境確認用）")
        print("=" * 55)
        run_keyboard_teleop()
        raise SystemExit

    if args.mode in ("train", "traindemo"):
        _backend = {"cpu": gs.cpu, "metal": gs.metal, "cuda": gs.cuda, "gpu": gs.gpu}.get(
            args.backend, gs.cpu
        )
        model, SAVE_DIR = train(
            n_parallel=args.n_envs,
            show_viewer=not args.no_viewer,
            backend=_backend,
        )

    if args.mode in ("demo", "traindemo"):
        if args.mode == "demo":
            candidates = [
                os.path.join(SAVE_DIR, "ppo_so101_final.zip"),
                os.path.join(SAVE_DIR, "best_model.zip"),
            ]
            model_path = args.model_path or next(
                (p for p in candidates if os.path.exists(p)), None
            )
            if not model_path:
                print("⚠️ モデルが見つかりません。先に --mode train を実行してください。")
                raise SystemExit
            print(f"モデルをロード: {model_path}")
            model = PPO.load(model_path, device="cpu")

        run_viewer_demo(model, n_episodes=args.episodes)

    print("\n✅ 完了!")
    if args.mode in ("train", "traindemo"):
        print(f"\n📊 TensorBoard で学習曲線を確認:")
        print(f"  tensorboard --logdir {SAVE_DIR}/logs")
