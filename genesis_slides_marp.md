---
marp: true
theme: default
paginate: true
backgroundColor: #0A0E1A
color: #FFFFFF
style: |
  section {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    padding: 30px 50px;
    font-size: 0.75em;
  }
  h1 {
    color: #00D4FF;
    font-size: 1.5em;
    border-bottom: 2px solid #00D4FF;
    padding-bottom: 8px;
    margin-bottom: 10px;
  }
  h2 {
    color: #00D4FF;
    font-size: 1.15em;
    margin: 8px 0 4px;
  }
  h3 {
    color: #10B981;
    font-size: 0.95em;
    margin: 6px 0 4px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78em;
  }
  th {
    background: #1E2A4A;
    color: #00D4FF;
    padding: 5px 10px;
  }
  td {
    background: #0F1629;
    padding: 5px 10px;
    border-bottom: 1px solid #1E2A4A;
  }
  code {
    background: #0D1117;
    color: #10B981;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.82em;
  }
  pre {
    background: #0D1117 !important;
    border: 1px solid #1E2A4A;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 0.72em;
  }
  pre code {
    color: #10B981;
    font-size: 1em;
  }
  blockquote {
    border-left: 3px solid #7C3AED;
    background: #141C35;
    padding: 5px 12px;
    margin: 8px 0;
    color: #94A3B8;
    font-style: italic;
    font-size: 0.85em;
  }
  ul, ol {
    margin: 4px 0;
    padding-left: 1.4em;
  }
  li {
    margin: 3px 0;
    color: #94A3B8;
  }
  strong { color: #FFFFFF; }
  p { margin: 4px 0; }
  .cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-top: 8px;
  }
  .img-box {
    background: #141C35;
    border: 2px dashed #1E2A4A;
    border-radius: 8px;
    overflow: hidden;
    min-height: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .img-box img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 6px;
  }
  .section-divider {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
  }
  .section-divider h1 {
    font-size: 2.8em;
    border: none;
    color: #FFFFFF;
  }
  .section-divider h2 {
    color: #94A3B8;
    font-weight: normal;
    font-size: 1em;
  }
  .chapter-tag {
    display: inline-block;
    background: #00D4FF22;
    border: 1px solid #00D4FF;
    color: #00D4FF;
    padding: 3px 14px;
    border-radius: 4px;
    font-size: 0.65em;
    margin-bottom: 14px;
    letter-spacing: 0.08em;
  }
  section.title {
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  section.title h1 {
    font-size: 3em;
    border: none;
    color: #FFFFFF;
    margin-bottom: 6px;
  }
  section.title h2 {
    color: #00D4FF;
    font-size: 1.3em;
    font-weight: bold;
  }
  section.title h3 {
    color: #94A3B8;
    font-size: 0.9em;
    font-weight: normal;
  }
  .tag {
    display: inline-block;
    background: #7C3AED44;
    border: 1px solid #7C3AED;
    color: #FFFFFF;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.65em;
    margin-bottom: 12px;
  }
---

<!-- ============================================================ -->
<!--  CHAPTER 0 : タイトル                                        -->
<!-- ============================================================ -->

<!-- _class: title -->

<div class="tag">Physical AI Platform</div>

# Genesis
## 次世代 物理シミュレーター
### ロボット学習のための汎用物理エンジン

2024年発表 | MIT License | ETH Zurich / CMU

<div class="img-box">

![Screen](./images/chapter1.gif)

</div>

---

<!-- ============================================================ -->
<!--  CHAPTER 1 : Genesisの説明                                   -->
<!-- ============================================================ -->

<!-- _class: section-divider -->

<div class="chapter-tag">CHAPTER 1</div>

# Genesisとは何か
## — 概要・背景・できること

---

# Genesisとは？

<div class="cols">
<div>

ロボティクス・具現化AI研究のために設計された**汎用物理シミュレーションプラットフォーム**。

| 特徴 | 概要 |
|------|------|
| 🌍 汎用物理エンジン | 剛体・流体・弾性体・布・粒子をシミュレーション |
| ⚡ 超高速並列計算 | GPU並列で従来比 **最大4万3000倍** |
| 🤖 AI/ML対応 | 強化学習・模倣学習・世界モデル訓練に最適化 |
| 🔓 オープンソース | MIT License。研究・商用利用が可能 |

</div>
<div class="img-box">

![Screen](./images/chapter1.gif)

</div>
</div>

---

# なぜGenesisが必要か

<div class="cols">
<div>

### ❌ 従来の課題
- シミュレーターごとに別々のAPIが必要
- 物質ごとに異なるエンジンを使い分け
- シミュレーション速度がボトルネック
- 現実との乖離（Sim-to-Real Gap）

### ✅ Genesisの解決策
- 統一APIで全物質・全ロボットを制御
- 単一エンジンで剛体・流体・粒子に対応
- GPU並列で最大 **4.3万倍** の高速化
- pip一発でインストール完了

</div>
<div class="img-box">

![Screen](./images/chapter1.gif)

</div>
</div>

---

# 圧倒的なシミュレーション速度

<div class="cols">
<div>

## **43,000×** — Isaac Gymより高速

> RTX 4090 × 26,000並列環境

| エンジン | 相対速度 |
|----------|----------|
| MuJoCo (CPU) | 1× |
| Isaac Gym (GPU) | ~300× |
| **Genesis (GPU)** | **43,000×** |

**並列環境数**: 10,000+ ／ **初期化**: 0.01 sec

</div>
<div class="img-box">

![Screen](./images/chapter1.gif)

</div>
</div>

---

# アーキテクチャ概要

<div class="cols">
<div>

```
┌──────────────────────────────┐
│       Python API Layer       │
│  genesis.Scene / Robot / ... │
├──────────────────────────────┤
│         Solver Layer         │
│  Rigid · SPH · MPM · FEM    │
├──────────────────────────────┤
│        Rendering Layer       │
│  Ray Tracing / Raster / GL   │
├──────────────────────────────┤
│        Hardware Layer        │
│  CUDA GPU · CPU · Multi-GPU  │
└──────────────────────────────┘
```

統一API・統一データ構造で全レイヤーが連携。

</div>
<div class="img-box">

![Screen](./images/chapter1.gif)

</div>
</div>

---

<!-- ============================================================ -->
<!--  CHAPTER 2 : 素材・扱える種類                                -->
<!-- ============================================================ -->

<!-- _class: section-divider -->

<div class="chapter-tag">CHAPTER 2</div>

# 素材・扱える物理現象
## — 6種類のソルバーと統合シミュレーション

---

# 対応する物理現象 — 6種のソルバー

<div class="cols">
<div>

| ソルバー | 対象物質 | 主なユースケース |
|----------|---------|----------------|
| 🧱 剛体 (Rigid Body) | 衝突・摩擦・関節 | ロボット本体・物体操作 |
| 💧 流体 (SPH) | 液体・ガス | 環境との相互作用 |
| 🧊 弾性体 (MPM) | ゴム・粘土・ゲル | 軟体接触のリアル再現 |
| 🧵 布 (FEM) | 衣服・シート・膜 | 繊維の物理的振る舞い |
| ✨ 粒子 (PBD) | 砂・雪・粉体 | バルク材料の取り扱い |
| ⚙️ ハイブリッド結合 | 上記すべて連成 | 異素材の同時シミュレーション |

</div>
<div class="img-box">

![Screen](./images/chapter2.gif)

</div>
</div>

---

# ロボット制御での活用

<div class="cols">
<div>

```python
import genesis as gs

gs.init(backend=gs.cuda)
scene = gs.Scene(sim_freq=100)

robot = scene.add_entity(
    gs.morphs.MJCF(file="franka.xml")
)

scene.build(n_envs=1000)
for step in range(10000):
    scene.step()
```

| カテゴリ | 内容 |
|----------|------|
| 対応形式 | URDF / MJCF / SRDF |
| センサー | カメラ・深度・力覚・IMU |
| 連携 | Isaac Lab / LeRobot / SB3 |

</div>
<div class="img-box">

![Screen](./images/chapter2-1.gif)

</div>
</div>

---

# 競合比較

<div class="cols">
<div>

| 機能 | MuJoCo | Isaac Gym | PyBullet | **Genesis** |
|------|--------|-----------|----------|-------------|
| 物理ソルバー統合 | 部分的 | 剛体のみ | 剛体のみ | ✅ 全種類 |
| GPU並列 | ❌ | ✅ | ❌ | ✅ |
| 流体シミュ | ❌ | ❌ | ❌ | ✅ |
| 軟体シミュ | ❌ | ❌ | ❌ | ✅ |
| 速度（相対） | 1× | ~300× | 0.5× | **43,000×** |
| ライセンス | Apache | ❌ 非商用 | zlib | ✅ MIT |
| インストール | 複雑 | 複雑 | pip | ✅ pip |

</div>
<div class="img-box">

![Screen](./images/chapter2-2.gif)

</div>
</div>

---

<!-- ============================================================ -->
<!--  CHAPTER 3 : Go2で学習の仕方                                 -->
<!-- ============================================================ -->

<!-- _class: section-divider -->

<div class="chapter-tag">CHAPTER 3</div>

# Go2で学ぶ強化学習の仕方
## — Genesisの公式サンプルを読み解く

---

# Go2 四足歩行ロボット学習の概要

<div class="cols">
<div>

> 公式サンプル `examples/locomotion/go2_train.py`

### Unitree Go2とは
- 12自由度の四足歩行ロボット（各脚 Hip / Thigh / Calf）
- 歩行・走行・段差乗り越えが可能
- 産学研究で広く使われるリファレンス機体

### このサンプルで学習すること
1. 前進速度 **0.5 m/s** を追従するポリシー
2. **4,096並列環境** でGPU高速学習
3. **101イテレーション** で歩行ポリシーを取得
4. `rsl_rl` の OnPolicyRunner を使用

</div>
<div class="img-box">

![Screen](./images/chapter3.gif)

</div>
</div>

---

# Go2 環境設定 — ロボット構成

<div class="cols">
<div>

### 関節構成（12 DOF）

| 脚 | Hip | Thigh | Calf |
|----|-----|-------|------|
| FR（右前） | 0.0 rad | 0.8 rad | −1.5 rad |
| FL（左前） | 0.0 rad | 0.8 rad | −1.5 rad |
| RR（右後） | 0.0 rad | 1.0 rad | −1.5 rad |
| RL（左後） | 0.0 rad | 1.0 rad | −1.5 rad |

### 制御パラメータ

| 項目 | 値 |
|------|-----|
| 制御方式 | PD制御（位置制御） |
| Kp（比例ゲイン） | 20.0 |
| Kd（微分ゲイン） | 0.5 |
| Action Scale | 0.25（出力を±25%に制限） |
| 初期高さ | Z = 0.42 m ／ エピソード長 20秒 |

</div>
<div class="img-box">

![Screen](./images/chapter3.gif)

</div>
</div>

---

# Go2 観測空間（45次元）

<div class="cols">
<div>

```python
obs_cfg = {
    "num_obs": 45,
    "obs_scales": {
        "lin_vel":  2.0,   # 線形速度を強調
        "ang_vel":  0.25,  # 角速度は小さくスケール
        "dof_pos":  1.0,
        "dof_vel":  0.05,  # 関節速度は小さくスケール
    },
}
```

| 観測項目 | 次元 | スケール |
|----------|------|---------|
| ベース線形速度 (x,y,z) | 3 | × 2.0 |
| ベース角速度 (roll,pitch,yaw) | 3 | × 0.25 |
| 重力ベクトル | 3 | × 1.0 |
| 速度コマンド (vx,vy,ωz) | 3 | × 1.0 |
| 関節角度（12DOF） | 12 | × 1.0 |
| 関節速度（12DOF） | 12 | × 0.05 |
| 前ステップアクション | 12 | × 1.0 |

> 転倒終了条件：roll / pitch が **10度超過** で即リセット

</div>
<div class="img-box">

![Screen](./images/chapter3.gif)

</div>
</div>

---

# Go2 報酬設計

<div class="cols">
<div>

```python
reward_cfg = {
    "tracking_sigma": 0.25,
    "base_height_target": 0.3,    # 目標体高 30cm
    "reward_scales": {
        "tracking_lin_vel":  1.0,   # ①速度追従（正）
        "tracking_ang_vel":  0.2,   # ②角速度追従（正）
        "lin_vel_z":        -1.0,   # ③上下バウンド罰則
        "base_height":     -50.0,   # ④体高維持（強罰則）
        "action_rate":     -0.005,  # ⑤急激な動作の抑制
        "similar_to_default": -0.1, # ⑥自然な姿勢維持
    },
}
```

| # | 報酬項目 | 符号 | 役割 |
|---|----------|------|------|
| ① | 速度追従 | ＋ | 目標速度 0.5m/s への追従 |
| ③ | Z速度 | − | 無駄な上下動を抑制 |
| ④ | 体高維持 | − | 低姿勢・転倒を強く罰則（×-50） |
| ⑤ | 動作変化率 | − | 滑らかな動作を促進 |

</div>
<div class="img-box">

![Screen](./images/chapter3.gif)

</div>
</div>

---

# Go2 PPO学習設定

<div class="cols">
<div>

```python
"policy": {
    "activation": "elu",
    "actor_hidden_dims":  [512, 256, 128],
    "critic_hidden_dims": [512, 256, 128],
    "init_noise_std": 1.0,
}
"algorithm": {
    "clip_param": 0.2,
    "desired_kl": 0.01,    # 適応的LR制御
    "entropy_coef": 0.01,
    "schedule": "adaptive",
    "num_learning_epochs": 5,
    "num_mini_batches": 4,
}
```

### 実行コマンド

```bash
python examples/locomotion/go2_train.py \
  -e go2-walking -B 4096 --max_iterations 101
```

| イテレーション | 状況 |
|---------------|------|
| 0〜10 | ランダム動作・転倒が多い |
| 10〜30 | 立ち上がり・体高維持が安定化 |
| 30〜70 | 歩行パターンが出現 |
| 70〜101 | 収束。0.5 m/s での安定歩行 |

</div>
<div class="img-box">

![Screen](./images/chapter3.gif)

</div>
</div>

---

<!-- ============================================================ -->
<!--  CHAPTER 4 : 強化学習の種類                                  -->
<!-- ============================================================ -->

<!-- _class: section-divider -->

<div class="chapter-tag">CHAPTER 4</div>

# 強化学習の種類
## — ロボット学習で使われる主なアルゴリズム

---

# 強化学習アルゴリズムの全体像

<div class="cols">
<div>

### モデルフリー — On-Policy

| 手法 | 特徴 | 用途 |
|------|------|------|
| **PPO** | 安定・高速・並列に強い | Go2歩行・SO-101把持 |
| TRPO | 理論的に堅牢・低速 | 精密タスク |
| A3C | 非同期並列・シンプル | 研究・検証 |

### モデルフリー — Off-Policy

| 手法 | 特徴 | 用途 |
|------|------|------|
| SAC | サンプル効率が高い | 連続制御全般 |
| TD3 | Critic安定化に強い | マニピュレーション |
| DQN | 離散行動空間向け | 経路選択・分類 |

> Genesisの並列環境は **On-Policy（PPO）と最も相性が良い**。
> 大量のサンプルを一気に収集して捨てる設計のため。

</div>
<div class="img-box">

![Screen](./images/chapter4.gif)

</div>
</div>

---

# なぜGenesisではPPOが主流か

<div class="cols">
<div>

### PPO（Proximal Policy Optimization）の強み

- **並列サンプル収集と相性が良い**  
  4,096環境 × 24ステップ = 約10万サンプルを一括取得
- **実装がシンプルで安定**  
  `rsl_rl` / `stable-baselines3` で即使用可能
- **ハイパーパラメータが少ない**  
  `clip_param=0.2` と `learning_rate` が主な調整箇所
- **Adaptive KLでLRを自動調整**  
  `desired_kl=0.01` で更新量を自動的に制御

### 模倣学習・その他との組み合わせ

| 手法 | 概要 |
|------|------|
| ACT / Diffusion Policy | デモデータから直接学習 |
| PPO + 模倣学習の初期化 | デモで初期化 → PPOで改善 |
| RLHF的アプローチ | 人間フィードバックで報酬を調整 |

</div>
<div class="img-box">

![Screen](./images/chapter4.gif)

</div>
</div>

---

<!-- ============================================================ -->
<!--  CHAPTER 5 : スパース報酬 vs 報酬シェイピング                -->
<!-- ============================================================ -->

<!-- _class: section-divider -->

<div class="chapter-tag">CHAPTER 5</div>

# スパース報酬 vs 報酬シェイピング
## — 報酬設計がなぜ学習を左右するのか

---

# 報酬シェイピングとは

<div class="cols">
<div>

> 「AIに何を頑張ってほしいかを、段階的なヒントとして報酬に埋め込む設計技術」

### ❌ スパース報酬だけの場合
- 成功（+30）以外は報酬ゼロ → 勾配が流れない
- 何百万ステップも学習が進まない
- 学習曲線：**長時間フラット → 突然上昇（不安定）**

### ✅ 報酬シェイピングを使う場合
- 毎ステップ「方向性ある報酬」が得られる
- アームが近づく → 報酬上昇で勾配が流れる
- 学習曲線：**序盤から緩やかに上昇 → 安定収束**

</div>
<div class="img-box">

![Screen](./images/chapter4.gif)

</div>
</div>

---

# スパース報酬 vs 報酬シェイピング — 比較

<div class="cols">
<div>

| 観点 | スパース報酬 | 報酬シェイピング |
|------|-------------|-----------------|
| 報酬タイミング | 成功時のみ | 毎ステップ |
| 学習初期 | 停滞しやすい | 勾配が常に存在 |
| 探索効率 | ランダム探索 | 目的指向の探索 |
| 学習速度 | 非常に遅い | 数倍〜数十倍速い |
| 設計難易度 | 簡単 | 難しい（副作用注意） |
| リスク | 学習が進まない | **報酬ハッキング** |

> ⚠️ **報酬ハッキング**：AIが意図しない方法で高スコアを取ることがある。  
> Go2では「体を地面に這わせて前進」、SO-101では「テーブルを揺らして高さを稼ぐ」など。  
> 報酬設計は実験と検証の繰り返し。

</div>
<div class="img-box">

![Screen](./images/chapter4.gif)

</div>
</div>

---

<!-- ============================================================ -->
<!--  CHAPTER 6 : SO-101で並列を作ってみた                        -->
<!-- ============================================================ -->

<!-- _class: section-divider -->

<div class="chapter-tag">CHAPTER 6</div>

# SO-101で並列学習を作ってみた
## — genesis-so101-arm-demo 実装解説

---

# SO-101 × Genesis の概要

<div class="cols">
<div>

> 🔗 github.com/oggata/genesis-so101-arm-demo

### SO-101 ロボットアームとは
- HuggingFace製OSS **6DOF**ロボットアーム
- 低コスト（数万円〜）で実機購入可能
- URDF形式で物理シミュに直接ロード可
- LeRobot・ACT・Diffusion Policyと連携
- Sim2Real研究のデファクトスタンダード化

### このデモで実現すること
1. キューブ把持タスクを**PPO強化学習**
2. **5〜50並列環境**で同時学習（GPU加速）
3. OVERHEAD / WRISTの**2カメラ視点**
4. TensorBoardでリアルタイム学習曲線確認

</div>
<div class="img-box">

![Screen](./images/chapter5.gif)

</div>
</div>

---

# システム構成 — GenesisParallelVecEnv

<div class="cols">
<div>

```
SO-101 URDF → Genesis Scene → PPO (SB3) → VecMonitor
HuggingFace    n_envs並列      カスタム      報酬・成功率
自動DL         ビルド          MLP Policy    ログ
```

```python
# 1シーンに複数ロボットをグリッド配置
scene.build(
    n_envs=N,
    env_spacing=(0.7, 0.7)
)
```

| パラメータ | 値 |
|------------|-----|
| アルゴリズム | PPO |
| ポリシー | カスタムMLP (256→256→256) |
| 並列環境数 | 5〜50（`--n_envs` で指定） |
| 総ステップ数 | 300,000 steps |
| learning_rate | 3e-4（線形スケジュール） |
| gamma / lambda | 0.99 / 0.95（GAE） |

</div>
<div class="img-box">

![Screen](./images/chapter5-1.gif)

</div>
</div>

---

# 報酬関数の実装

<div class="cols">
<div>

```python
# 最近傍キューブまでの距離
dists = np.linalg.norm(cube_poss - eef, axis=1)
nearest_z = cube_poss[nearest_idx, 2]

# 報酬計算（報酬シェイピング）
rewards[i] = (
    -dists[nearest_idx] * 1.5          # ①距離罰則
  + max(0.0, nearest_z - 0.02) * 8.0  # ②高さ報酬
  + (30.0 if success else 0.0)         # ③成功ボーナス
  - 0.01                                # ④時間ペナルティ
)

# 成功条件（スパース）
success = nearest_z > CUBE_LIFT_HEIGHT  # 0.07m
```

| # | 名前 | 係数 | 役割 |
|---|------|------|------|
| ① | 距離罰則 | × 1.5 | EEFとキューブが近いほど高報酬 |
| ② | 高さ報酬 | × 8.0 | Z=0.02m以上浮くほど加算 |
| ③ | 成功ボーナス | +30.0 | 0.07m到達でスパースボーナス |
| ④ | 時間ペナルティ | −0.01 | 素早い解決を促進 |

</div>
<div class="img-box">

![Screen](./images/chapter5-2.gif)

</div>
</div>

---

# Go2 vs SO-101 — 設計の比較

<div class="cols">
<div>

| 項目 | Go2 | SO-101 |
|------|-----|--------|
| ロボット形式 | 四足歩行 | 6DOFアーム |
| 並列環境数 | **4,096** | 5〜50 |
| ネットワーク | 512→256→128 | 256→256→256 |
| 活性化関数 | ELU | ReLU |
| LRスケジュール | Adaptive KL | 線形 |
| アクション次元 | **12 DOF** | 6 DOF |
| 観測次元 | **45** | カスタム |
| 学習ライブラリ | rsl_rl | stable-baselines3 |
| 報酬の複雑さ | 6項目（姿勢・速度・高さ） | 4項目（距離・高さ・成功・時間） |

> 四足歩行は**姿勢安定**が最重要 → `base_height: -50.0` の強い罰則。  
> アーム把持は**到達と持ち上げ**が主眼 → 距離と高さの密な報酬。

</div>
<div class="img-box">

![Screen](./images/chapter5-2.gif)

</div>
</div>