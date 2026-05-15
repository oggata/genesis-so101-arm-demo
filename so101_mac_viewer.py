# ============================================================
# Genesis SO-101アーム - 強化学習（PPO）Mac ビューワー版
# リアルタイムビューワーでシミュレーションを可視化
# ============================================================

# ============================================================
# STEP 0: 依存ライブラリのインストール（初回のみ）
# ============================================================
# pip install genesis-world stable-baselines3 gymnasium opencv-python

# ============================================================
# STEP 1: インポート
# ============================================================
import genesis as gs
import numpy as np
import torch
import torch.nn as nn
import os
import re
import urllib.request
import matplotlib
matplotlib.use("Agg")   # ビューワーと競合しないバックエンド
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
import gymnasium as gym
from gymnasium import spaces

# ============================================================
# STEP 2: SO-101 URDFをダウンロード（初回のみ）
# ============================================================
URDF_DIR  = os.path.join(os.path.dirname(__file__), "so101_urdf")
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
# STEP 3: 学習用環境クラス（show_viewer=False、高速化優先）
# ============================================================
CAM_W, CAM_H = 320, 240   # 学習時は小さめで省メモリ

class SO101GraspEnv(gym.Env):
    """
    SO-101ロボットアームがキューブを把持して持ち上げるRL環境
    学習用（show_viewer=False）
    """
    metadata = {"render_modes": ["rgb_array"]}

    N_CUBES          = 5
    MAX_STEPS        = 500
    CUBE_LIFT_HEIGHT = 0.07
    ACTION_SCALE     = 0.05
    DT               = 0.01

    CUBE_X_MIN, CUBE_X_MAX = 0.05, 0.18
    CUBE_Y_MIN, CUBE_Y_MAX = -0.25, -0.02

    def __init__(self, render_mode=None, env_id=0):
        super().__init__()
        self.render_mode = render_mode
        self.env_id      = env_id
        self._step_count = 0

        try:
            gs.init(backend=gs.cpu, logging_level="warning")
        except Exception:
            pass

        self._build_scene()

        n = self.n_dofs
        obs_dim = 2 * n + 3 + self.N_CUBES * 3 + self.N_CUBES + 1
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space      = spaces.Box(-1.0, 1.0, shape=(n,), dtype=np.float32)

    def _build_scene(self):
        self.scene = gs.Scene(
            sim_options=gs.options.SimOptions(dt=self.DT, substeps=5),
            show_viewer=False,   # 学習中はビューワー非表示
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

        self.scene.build()
        self.n_dofs = self.robot.n_dofs
        print(f"✓ 学習環境構築完了 (DoF={self.n_dofs}, キューブ={self.N_CUBES}個)")

    def _get_eef_pos(self) -> np.ndarray:
        try:
            return self.robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            return np.array([0.10, -0.15, 0.28], dtype=np.float32)

    def _get_cube_positions(self) -> np.ndarray:
        return np.stack([c.get_pos().cpu().numpy() for c in self.cubes])

    def _get_obs(self) -> np.ndarray:
        qpos      = self.robot.get_dofs_position().cpu().numpy()
        qvel      = self.robot.get_dofs_velocity().cpu().numpy()
        eef_pos   = self._get_eef_pos()
        cube_poss = self._get_cube_positions()
        dists     = np.linalg.norm(cube_poss - eef_pos, axis=1)
        nearest   = np.array([float(np.argmin(dists))])
        return np.concatenate([qpos, qvel, eef_pos, cube_poss.flatten(), dists, nearest]).astype(np.float32)

    def _compute_reward(self):
        eef_pos      = self._get_eef_pos()
        cube_poss    = self._get_cube_positions()
        dists        = np.linalg.norm(cube_poss - eef_pos, axis=1)
        nearest_idx  = int(np.argmin(dists))
        nearest_dist = dists[nearest_idx]
        nearest_z    = float(cube_poss[nearest_idx, 2])

        reward_reach   = -nearest_dist * 1.5
        reward_lift    = max(0.0, nearest_z - 0.02) * 8.0
        success        = nearest_z > self.CUBE_LIFT_HEIGHT
        reward_success = 30.0 if success else 0.0

        return float(reward_reach + reward_lift + reward_success - 0.01), success

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._step_count = 0
        rng = np.random.default_rng(seed)

        self.robot.set_dofs_position(np.zeros(self.n_dofs, dtype=np.float32))
        self.robot.set_dofs_velocity(np.zeros(self.n_dofs, dtype=np.float32))

        for cube in self.cubes:
            cx = rng.uniform(self.CUBE_X_MIN, self.CUBE_X_MAX)
            cy = rng.uniform(self.CUBE_Y_MIN, self.CUBE_Y_MAX)
            cube.set_pos(np.array([cx, cy, 0.02], dtype=np.float32))
            cube.set_quat(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))

        for _ in range(10):
            self.scene.step()

        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        self._step_count += 1
        current_qpos = self.robot.get_dofs_position().cpu().numpy()
        delta        = np.clip(action, -1.0, 1.0) * self.ACTION_SCALE
        target_qpos  = np.clip(current_qpos + delta, -np.pi, np.pi)
        self.robot.set_dofs_position(target_qpos.astype(np.float32))
        self.scene.step()

        obs = self._get_obs()
        reward, success = self._compute_reward()
        terminated = success
        truncated  = self._step_count >= self.MAX_STEPS
        return obs, reward, terminated, truncated, {"success": success}

    def close(self):
        pass


# ============================================================
# STEP 4: リアルタイム・デモ環境クラス（show_viewer=True）
# ============================================================
class SO101ViewerEnv:
    """
    Macのビューワーでリアルタイム確認用。
    学習済みモデルを使ってデモ再生する。
    """
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
                camera_lookat=(0.15, 0.0, 0.1),
                camera_fov=50,
                max_FPS=60,
            ),
            show_viewer=True,    # ← Macビューワーを有効化
            show_FPS=True,
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

        colors = [
            (1.0, 0.3, 0.3), (0.3, 1.0, 0.3), (0.3, 0.3, 1.0),
            (1.0, 1.0, 0.3), (1.0, 0.5, 0.0),
        ]
        self.cubes = [
            self.scene.add_entity(
                material=gs.materials.Rigid(rho=300),
                morph=gs.morphs.Box(size=(0.04, 0.04, 0.04), pos=p, fixed=False),
                surface=gs.surfaces.Default(color=(*c, 1.0)),
            )
            for p, c in zip(
                [(0.12,-0.08,0.02),(0.12,0.08,0.02),(0.16,0.0,0.02),(0.18,-0.08,0.02),(0.18,0.08,0.02)],
                colors,
            )
        ]

        self.scene.build()
        self.n_dofs = self.robot.n_dofs
        print(f"✓ ビューワー環境構築完了 (DoF={self.n_dofs})")

    def _get_eef_pos(self) -> np.ndarray:
        try:
            return self.robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            return np.array([0.10, -0.15, 0.28], dtype=np.float32)

    def _get_cube_positions(self) -> np.ndarray:
        return np.stack([c.get_pos().cpu().numpy() for c in self.cubes])

    def _get_obs(self) -> np.ndarray:
        qpos      = self.robot.get_dofs_position().cpu().numpy()
        qvel      = self.robot.get_dofs_velocity().cpu().numpy()
        eef_pos   = self._get_eef_pos()
        cube_poss = self._get_cube_positions()
        dists     = np.linalg.norm(cube_poss - eef_pos, axis=1)
        nearest   = np.array([float(np.argmin(dists))])
        return np.concatenate([qpos, qvel, eef_pos, cube_poss.flatten(), dists, nearest]).astype(np.float32)

    def reset(self, seed=None):
        rng = np.random.default_rng(seed)
        self.robot.set_dofs_position(np.zeros(self.n_dofs, dtype=np.float32))
        self.robot.set_dofs_velocity(np.zeros(self.n_dofs, dtype=np.float32))

        for cube in self.cubes:
            cx = rng.uniform(self.CUBE_X_MIN, self.CUBE_X_MAX)
            cy = rng.uniform(self.CUBE_Y_MIN, self.CUBE_Y_MAX)
            cube.set_pos(np.array([cx, cy, 0.02], dtype=np.float32))
            cube.set_quat(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))

        for _ in range(10):
            self.scene.step()

        return self._get_obs()

    def step(self, action: np.ndarray):
        current_qpos = self.robot.get_dofs_position().cpu().numpy()
        delta        = np.clip(action, -1.0, 1.0) * self.ACTION_SCALE
        target_qpos  = np.clip(current_qpos + delta, -np.pi, np.pi)
        self.robot.set_dofs_position(target_qpos.astype(np.float32))
        self.scene.step()

        obs       = self._get_obs()
        cube_poss = self._get_cube_positions()
        dists     = np.linalg.norm(cube_poss - self._get_eef_pos(), axis=1)
        max_z     = float(cube_poss[:, 2].max())
        success   = max_z > self.CUBE_LIFT_HEIGHT
        return obs, success


# ============================================================
# STEP 5: カスタムネットワーク
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
# STEP 6: 学習
# ============================================================
def train():
    SAVE_DIR = os.path.join(os.path.dirname(__file__), "genesis_so101_rl")
    LOG_DIR  = os.path.join(SAVE_DIR, "logs")
    os.makedirs(SAVE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR,  exist_ok=True)

    N_ENVS = 4   # Mac CPUに合わせて並列数を削減（Colabの64→4）
    print(f"\n並列環境数: {N_ENVS}  保存先: {SAVE_DIR}\n")

    def make_env(env_id):
        def _init():
            return SO101GraspEnv(env_id=env_id)
        return _init

    envs = VecMonitor(DummyVecEnv([make_env(i) for i in range(N_ENVS)]), LOG_DIR)

    policy_kwargs = dict(
        features_extractor_class=CustomMLP,
        features_extractor_kwargs=dict(features_dim=256),
        net_arch=dict(pi=[256, 128], vf=[256, 128]),
        activation_fn=nn.Tanh,
    )

    model = PPO(
        policy="MlpPolicy", env=envs,
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
            model = PPO.load(checkpoint_path, env=envs, device="cpu")
            print(f"✓ チェックポイントをロード: {checkpoint_path}")
        except ValueError as e:
            print(f"⚠️ 観測空間不一致のため新規学習: {e}")
            import shutil
            shutil.move(checkpoint_path, checkpoint_path.replace(".zip", "_old.zip"))

    checkpoint_cb = CheckpointCallback(
        save_freq=10_000, save_path=SAVE_DIR, name_prefix="ppo_so101"
    )
    eval_env = VecMonitor(DummyVecEnv([make_env(99)]))
    eval_cb  = EvalCallback(
        eval_env, best_model_save_path=SAVE_DIR, log_path=LOG_DIR,
        eval_freq=20_000, n_eval_episodes=10, deterministic=True, render=False,
    )

    TOTAL_TIMESTEPS = 60_000
    print(f"学習開始: {TOTAL_TIMESTEPS:,} ステップ\n")
    model.learn(
        total_timesteps=TOTAL_TIMESTEPS,
        callback=[checkpoint_cb, eval_cb],
        tb_log_name="ppo_so101",
        reset_num_timesteps=False,
    )

    final_path = os.path.join(SAVE_DIR, "ppo_so101_final")
    model.save(final_path)
    print(f"\n✓ 学習完了! モデル保存: {final_path}.zip")

    envs.close()
    eval_env.close()
    return model, SAVE_DIR


# ============================================================
# STEP 7: キーボードテレオペモード（環境確認用）
# ============================================================
"""
キーボード操作マッピング（SO-101 各関節）:
  F1 / F2   : Joint 0  (ベース回転)     +/-
  F3 / F4   : Joint 1  (肩ピッチ)       +/-
  F5 / F6   : Joint 2  (肘)             +/-
  F7 / F8   : Joint 3  (手首ピッチ)     +/-
  F9 / F10  : Joint 4  (手首ロール)     +/-
  - / =  : Joint 5  (グリッパー)     開/閉
  U         : リセット（キューブをランダム再配置）
  ESC       : 終了

  ※ viewer デフォルトキー（使わない）:
     i=ヘルプ  r=動画録画  s=画像保存  z=カメラリセット
"""

def run_keyboard_teleop():
    from genesis.vis.keybindings import Key, KeyAction, Keybind

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
            material=gs.materials.Rigid(
                friction=2.0,       # アーム表面の摩擦
                coup_friction=2.0,  # ブロックとの接触摩擦（把持に効く）
            ),
            morph=gs.morphs.URDF(file=URDF_PATH, pos=(0, 0, 0), fixed=True),
        )
        print("✓ SO-101 URDFをロード")
    except Exception as e:
        print(f"URDF読み込みエラー ({e})、Pandaで代替")
        robot = scene.add_entity(
            gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml")
        )

    colors = [
        (1.0, 0.3, 0.3), (0.3, 1.0, 0.3), (0.3, 0.3, 1.0),
        (1.0, 1.0, 0.3), (1.0, 0.5, 0.0),
    ]
    cube_positions = [
        (0.12, -0.08, 0.0125), (0.12,  0.08, 0.0125),
        (0.16,  0.00, 0.0125), (0.18, -0.08, 0.0125),
        (0.18,  0.08, 0.0125),
    ]
    cubes = [
        scene.add_entity(
            material=gs.materials.Rigid(
                rho=2000,              # 密度を上げて重くする（アルミ程度）
                friction=2.0,          # 剛体ソルバー内の摩擦（滑りにくく）
                coup_friction=2.0,     # グリッパーとの接触摩擦
                coup_restitution=0.3,  # 弾力（0=非弾性, 1=完全弾性）
            ),
            morph=gs.morphs.Box(size=(0.025, 0.025, 0.025), pos=p, fixed=False),
            surface=gs.surfaces.Default(color=(*c, 1.0)),
        )
        for p, c in zip(cube_positions, colors)
    ]

    # ──────────────────────────────────────────
    # カメラ追加（build()の前に追加する必要がある）
    # ──────────────────────────────────────────
    CAM_W, CAM_H = 400, 300

    # カメラ1: 真上からアーム全体を俯瞰
    cam_overhead = scene.add_camera(
        res=(CAM_W, CAM_H),
        pos=(0.15, 0.0, 1.2),
        lookat=(0.15, 0.0, 0.0),
        fov=55,
    )

    # カメラ2: グリッパー追従（毎ステップset_poseで更新）
    cam_wrist = scene.add_camera(
        res=(CAM_W, CAM_H),
        pos=(0.15, 0.0, 0.4),
        lookat=(0.15, 0.0, 0.0),
        fov=60,
    )

    scene.build()
    n_dofs = robot.n_dofs
    print(f"✓ シーン構築完了 (DoF={n_dofs})")

    def get_eef_pos():
        try:
            return robot.get_link("moving_jaw_so101_v1").get_pos().cpu().numpy()
        except Exception:
            return np.array([0.15, 0.0, 0.25], dtype=np.float32)

    def update_wrist_camera():
        """グリッパー位置に追従してwristカメラを更新"""
        eef = get_eef_pos()
        # アームの根元方向（原点）を常に向く
        cam_pos  = eef + np.array([0.0, 0.0, 0.12])   # グリッパーの12cm真上
        lookat   = eef + np.array([0.0, 0.0, -0.08])  # グリッパー先端下向き
        try:
            cam_wrist.set_pose(pos=cam_pos, lookat=lookat)
        except Exception:
            pass

    def grab_frame(cam):
        try:
            frame = cam.render(rgb=True)
            if isinstance(frame, (list, tuple)):
                frame = frame[0]
            if hasattr(frame, "cpu"):
                frame = frame.cpu().numpy()
            return frame.astype(np.uint8)
        except Exception:
            return np.zeros((CAM_H, CAM_W, 3), dtype=np.uint8)

    # OpenCVウィンドウ初期配置（メインビューワーの右側を想定）
    import cv2
    MAIN_WIN_W = 1000   # メインビューワーの幅の目安
    cv2.namedWindow("overhead", cv2.WINDOW_NORMAL)
    cv2.namedWindow("wrist",    cv2.WINDOW_NORMAL)
    cv2.resizeWindow("overhead", CAM_W, CAM_H)
    cv2.resizeWindow("wrist",    CAM_W, CAM_H)
    cv2.moveWindow("overhead", MAIN_WIN_W + 20, 50)
    cv2.moveWindow("wrist",    MAIN_WIN_W + 20, 50 + CAM_H + 40)

    # カメラ更新間隔（毎ステップだと重いので数ステップに1回）
    CAM_INTERVAL = 5
    step_count = 0

    print(__doc__)  # キー操作ガイドを表示

    dq = 0.03   # 1ステップあたりの関節角変化量

    # サーボ目標角度（現在位置で初期化）
    target_qpos = robot.get_dofs_position().cpu().numpy().astype(np.float32)

    # PD制御ゲイン（実機サーボの保持力をイメージ）
    KP = 200.0   # 位置ゲイン（大きいほど保持力強）
    KD = 20.0    # 速度ゲイン（振動を抑える）

    def move_joint(idx, delta):
        current = robot.get_dofs_position().cpu().numpy().astype(np.float32)
        target_qpos[idx] = float(np.clip(current[idx] + delta, -np.pi, np.pi))

    def apply_pd_control():
        """毎ステップ呼ぶ。目標角度に向けてトルクを出し続ける（サーボ保持）"""
        current_pos = robot.get_dofs_position().cpu().numpy().astype(np.float32)
        current_vel = robot.get_dofs_velocity().cpu().numpy().astype(np.float32)
        torque = KP * (target_qpos - current_pos) - KD * current_vel
        robot.control_dofs_force(torque)

    def reset_scene():
        target_qpos[:] = 0.0
        robot.set_dofs_position(target_qpos)
        rng = np.random.default_rng()
        for cube in cubes:
            cx = rng.uniform(0.05, 0.18)
            cy = rng.uniform(-0.25, -0.02)
            cube.set_pos(np.array([cx, cy, 0.0125], dtype=np.float32))
            cube.set_quat(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))
        print("↺ リセット完了")

    is_running = True
    def stop():
        nonlocal is_running
        is_running = False

    # DOFインデックスを安全に解決（DOF数に応じてクランプ）
    def dof(i):
        return min(i, n_dofs - 1)

    scene.viewer.register_keybinds(
        # Joint 0: F1(+) / F2(-)
        Keybind("j0_pos", Key.F1,  KeyAction.HOLD, callback=move_joint, args=(dof(0),  dq)),
        Keybind("j0_neg", Key.F2,  KeyAction.HOLD, callback=move_joint, args=(dof(0), -dq)),
        # Joint 1: F3(+) / F4(-)
        Keybind("j1_pos", Key.F3,  KeyAction.HOLD, callback=move_joint, args=(dof(1),  dq)),
        Keybind("j1_neg", Key.F4,  KeyAction.HOLD, callback=move_joint, args=(dof(1), -dq)),
        # Joint 2: F5(+) / F6(-)
        Keybind("j2_pos", Key.F5,  KeyAction.HOLD, callback=move_joint, args=(dof(2),  dq)),
        Keybind("j2_neg", Key.F6,  KeyAction.HOLD, callback=move_joint, args=(dof(2), -dq)),
        # Joint 3: F7(+) / F8(-)
        Keybind("j3_pos", Key.F7,  KeyAction.HOLD, callback=move_joint, args=(dof(3),  dq)),
        Keybind("j3_neg", Key.F8,  KeyAction.HOLD, callback=move_joint, args=(dof(3), -dq)),
        # Joint 4: F9(+) / F10(-)
        Keybind("j4_pos", Key.F9,  KeyAction.HOLD, callback=move_joint, args=(dof(4),  dq)),
        Keybind("j4_neg", Key.F10, KeyAction.HOLD, callback=move_joint, args=(dof(4), -dq)),
        # Joint 5 (グリッパー): -(+) / =(-)
        Keybind("j5_pos", Key.MINUS, KeyAction.HOLD, callback=move_joint, args=(dof(5),  dq)),
        Keybind("j5_neg", Key.EQUAL, KeyAction.HOLD, callback=move_joint, args=(dof(5), -dq)),
        # リセット・終了
        Keybind("reset", Key.U,      KeyAction.PRESS, callback=reset_scene),
        Keybind("quit",  Key.ESCAPE, KeyAction.PRESS, callback=stop),
    )

    try:
        while is_running:
            apply_pd_control()
            scene.step()

            # カメラ更新（数ステップに1回）
            step_count += 1
            if step_count % CAM_INTERVAL == 0:
                update_wrist_camera()

                img_overhead = grab_frame(cam_overhead)
                img_wrist    = grab_frame(cam_wrist)

                # ラベルを描画
                def draw_label(img, text):
                    cv2.rectangle(img, (0, 0), (len(text) * 11 + 10, 28), (0, 0, 0), -1)
                    cv2.putText(img, text, (6, 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 255), 1)
                    return img

                draw_label(img_overhead, "OVERHEAD")
                draw_label(img_wrist,    "WRIST")

                # RGB→BGR変換してOpenCVで表示
                cv2.imshow("overhead", cv2.cvtColor(img_overhead, cv2.COLOR_RGB2BGR))
                cv2.imshow("wrist",    cv2.cvtColor(img_wrist,    cv2.COLOR_RGB2BGR))
                cv2.waitKey(1)

    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        print("✓ キーボード操作モード終了")


# ============================================================
# STEP 8: リアルタイムビューワーでデモ再生
# ============================================================
def run_viewer_demo(model, n_episodes: int = 5):
    """
    学習済みモデルをMacビューワーでリアルタイム再生する。
    ビューワーウィンドウを閉じると終了。
    """
    print("\n--- Macビューワーでリアルタイムデモを開始 ---")
    print("ビューワーウィンドウを閉じると終了します。\n")

    env = SO101ViewerEnv()

    for ep in range(n_episodes):
        obs      = env.reset(seed=ep)
        done     = False
        total_r  = 0.0
        step     = 0
        MAX_STEP = 500

        print(f"Episode {ep + 1}/{n_episodes} 開始...")

        while not done and step < MAX_STEP:
            action, _ = model.predict(obs, deterministic=True)
            obs, success = env.step(action)
            step += 1

            if success:
                print(f"  ✓ SUCCESS! ({step}ステップ)")
                done = True

        if not done:
            print(f"  Episode {ep + 1}: {step}ステップ完了 (タイムアウト)")

    print("\n✓ デモ終了")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SO-101 RL Mac版",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["train", "demo", "traindemo"],
        default=None,
        help=(
            "（省略）      : キーボードで環境を手動確認\n"
            "train        : 学習のみ\n"
            "demo         : 既存モデルでビューワーデモ\n"
            "traindemo    : 学習後にビューワーデモ"
        ),
    )
    parser.add_argument(
        "--model_path",
        default=None,
        help="demo モード時に使う .zip モデルパス（省略時は自動検索）",
    )
    parser.add_argument(
        "--episodes", type=int, default=5,
        help="デモエピソード数（デフォルト: 5）",
    )
    args = parser.parse_args()

    SAVE_DIR = os.path.join(os.path.dirname(__file__), "genesis_so101_rl")

    # --------------------------------------------------
    # 引数なし → キーボードテレオペで環境確認
    # --------------------------------------------------
    if args.mode is None:
        print("=" * 50)
        print(" SO-101 キーボード操作モード（環境確認用）")
        print("=" * 50)
        run_keyboard_teleop()
        raise SystemExit

    # --------------------------------------------------
    # 学習
    # --------------------------------------------------
    if args.mode in ("train", "traindemo"):
        model, SAVE_DIR = train()

    # --------------------------------------------------
    # デモ
    # --------------------------------------------------
    if args.mode in ("demo", "traindemo"):
        if args.model_path:
            model_path = args.model_path
        else:
            candidates = [
                os.path.join(SAVE_DIR, "ppo_so101_final.zip"),
                os.path.join(SAVE_DIR, "best_model.zip"),
            ]
            model_path = next((p for p in candidates if os.path.exists(p)), None)

        if args.mode == "demo":
            if model_path and os.path.exists(model_path):
                print(f"モデルをロード: {model_path}")
                dummy_env = VecMonitor(DummyVecEnv([lambda: SO101GraspEnv()]))
                model = PPO.load(model_path, env=dummy_env, device="cpu")
                dummy_env.close()
            else:
                print("⚠️ モデルが見つかりません。先に --mode train を実行してください。")
                raise SystemExit

        run_viewer_demo(model, n_episodes=args.episodes)

    print("\n✅ 完了!")
    if args.mode in ("train", "traindemo"):
        print(f"\n📊 TensorBoard で学習曲線を確認:")
        print(f"  tensorboard --logdir {SAVE_DIR}/logs")
