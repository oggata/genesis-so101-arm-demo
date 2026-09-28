// Jev (TypeSafe AI) で SO-101 ブラウザシミュレーターを自律操作するサーバー
//
// ブラウザ（jev/index.html）が報告するアーム・キューブの状態を Jev に渡し、
// 「どのキューブを狙うか」「次の一手（前後左右上下 / 開く / 閉じる）」を
// 型付きの choice で選ばせて、キューブをトレイに運ばせる。
//
//   cp jev/.env.example jev/.env   （TYPESAFE_API_KEY を記入）
//   node jev/server-jev.js
//   → http://localhost:3000 を開いて「Start Jev」
//
//   JEV_MOCK=1 node jev/server-jev.js
//   → Jev を呼ばずに簡易ルールで代用（APIキーなしで動作確認する用）
//
// 依存パッケージなし（Node 18 以上）。
//
// 環境変数（jev/.env に書くか、コマンドの前に指定。コマンド側が優先）:
//   TYPESAFE_API_KEY  Jev の API キー（JEV_MOCK=1 以外では必須）
//   JEV_API_URL       default: https://api.typesafe.ai/v1/systemone
//   JEV_MODEL         default: jev-latest
//   JEV_MOCK          "1" で Jev を呼ばずに簡易ルールで動かす
//   JEV_AUTOSTART     "1" でブラウザ接続時に自動開始 (default: 無効)
//   JEV_TICK_MS       意思決定の間隔 (default: 300)
//   JEV_MAX_STEPS     最大意思決定回数 (default: 400)
//   JEV_CARRY_Z       運搬時の高さ cm (default: 5)
//   PORT              (default: 3000)

const http = require('http');
const fs = require('fs');
const path = require('path');

// jev/.env を読み込む（KEY=VALUE 形式。すでに環境変数で指定されている値が優先）
function loadEnv(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!m || process.env[m[1]] !== undefined) continue;
    process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, '$2');
  }
}
loadEnv(path.join(__dirname, '.env'));

const JEV_API_URL = process.env.JEV_API_URL || 'https://api.typesafe.ai/v1/systemone';
const JEV_API_KEY = process.env.TYPESAFE_API_KEY;
const JEV_MODEL = process.env.JEV_MODEL || 'jev-latest';
const MOCK = process.env.JEV_MOCK === '1';
const AUTOSTART = process.env.JEV_AUTOSTART === '1';
const TICK_MS = parseInt(process.env.JEV_TICK_MS || '300', 10);
const MAX_STEPS = parseInt(process.env.JEV_MAX_STEPS || '400', 10);
const PORT = parseInt(process.env.PORT || '3000', 10);
const COMMAND_TIMEOUT_MS = 30000;

// トレイ内の置き場所（トレイ中心からの相対 cm）。空いている所から順に使う
const TRAY_SLOTS = [[-2.5, -2.5], [2.5, -2.5], [-2.5, 2.5], [2.5, 2.5], [0, 0]];
// 運搬時の高さ(cm)。これより低いあいだは横移動を選択肢から外す。高すぎると遠くで腕が届かなくなる
const HOVER_Z = parseFloat(process.env.JEV_CARRY_Z || '5');
const GRASP_Z = 1.3;    // 掴む高さ = キューブ中心
const RELEASE_Z = 3.5;  // トレイ上で離す高さ
// 目標の真上・目標の高さとみなす許容誤差(cm)。0.5cm刻みで必ず入れるよう 0.25 より大きくする
const ALIGN_TOL = 0.3;
const within = (d) => Math.abs(d) <= ALIGN_TOL + 1e-6;   // 0.30000000000000004 対策

// 次の一手。キーが Jev の choice の選択肢になる
const ACTIONS = {
  forward_2cm:  { cmd: 'move_by 2 0 0',    desc: 'Move the gripper +2 cm in x (forward, away from the robot base). Useful when dx >= 2.' },
  back_2cm:     { cmd: 'move_by -2 0 0',   desc: 'Move the gripper -2 cm in x (back, toward the robot base). Useful when dx <= -2.' },
  left_2cm:     { cmd: 'move_by 0 2 0',    desc: 'Move the gripper +2 cm in y (left). Useful when dy >= 2.' },
  right_2cm:    { cmd: 'move_by 0 -2 0',   desc: 'Move the gripper -2 cm in y (right). Useful when dy <= -2.' },
  forward_05cm: { cmd: 'move_by 0.5 0 0',  desc: 'Fine move +0.5 cm in x. Useful when 0.3 < dx < 2.' },
  back_05cm:    { cmd: 'move_by -0.5 0 0', desc: 'Fine move -0.5 cm in x. Useful when -2 < dx < -0.3.' },
  left_05cm:    { cmd: 'move_by 0 0.5 0',  desc: 'Fine move +0.5 cm in y. Useful when 0.3 < dy < 2.' },
  right_05cm:   { cmd: 'move_by 0 -0.5 0', desc: 'Fine move -0.5 cm in y. Useful when -2 < dy < -0.3.' },
  up_2cm:       { cmd: 'move_by 0 0 2',    desc: 'Raise the gripper 2 cm. Do this before moving sideways while low, or when dz >= 1.' },
  down_2cm:     { cmd: 'move_by 0 0 -2',   desc: 'Lower the gripper 2 cm. Only when the gripper is already above the target (|dx| and |dy| <= 0.3) and dz <= -2. Never when task.phase says OPEN NOW or CLOSE NOW.' },
  down_05cm:    { cmd: 'move_by 0 0 -0.5', desc: 'Lower the gripper 0.5 cm. Only when above the target and -2 < dz < -0.2. Never when task.phase says OPEN NOW or CLOSE NOW.' },
  open:         { cmd: 'open',             desc: 'Open the gripper. Choose this when task.phase says OPEN NOW (releases the held cube into the tray), or when task.phase says "open the gripper".' },
  close:        { cmd: 'close',            desc: 'Close the gripper to grasp. Choose this only when task.phase says CLOSE NOW.' },
};

// ---------------------------------------------------------------------------
// ブラウザとの通信（SSE でコマンドを送り、POST で結果と状態を受け取る）
// ---------------------------------------------------------------------------

const sseClients = new Set();
let simState = null;           // ブラウザから届いた最新の状態
let simStateAt = 0;
let commandSeq = 0;
const pending = new Map();     // id -> resolve

function sendEvent(event, data, only) {
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of only ? [only] : sseClients) res.write(payload);
}

// ブラウザで robot.run(cmd) を実行し、結果の文字列を待つ
function runOnSim(cmd) {
  if (sseClients.size === 0) return Promise.reject(new Error('ブラウザが接続されていません'));
  const id = ++commandSeq;
  // 複数タブが開いていても実行するのは最後に接続したタブだけ
  const target = [...sseClients].at(-1);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`command timeout: ${cmd}`));
    }, COMMAND_TIMEOUT_MS);
    pending.set(id, (result) => { clearTimeout(timer); resolve(result); });
    sendEvent('command', { id, cmd }, target);
  });
}

// ---------------------------------------------------------------------------
// タスク: 状態の整理
// ---------------------------------------------------------------------------

const round1 = (v) => Math.round(v * 10) / 10;

function freeTraySlot(s) {
  for (const [ox, oy] of TRAY_SLOTS) {
    const x = s.tray_cm.x + ox, y = s.tray_cm.y + oy;
    const occupied = Object.entries(s.cubes_cm).some(([name, p]) =>
      s.in_tray.includes(name) && Math.hypot(p.x - x, p.y - y) < 2);
    if (!occupied) return { x, y };
  }
  return { x: s.tray_cm.x, y: s.tray_cm.y };
}

// 今の段階と、次に向かうべき点
function describeTask(s, targetCube) {
  const tcp = s.tcp_cm;
  const gripperOpen = s.joints.gripper >= 90;
  let phase, goal;
  // 目標の真上・目標の高さに着いたら「今すぐ開く/閉じる」をはっきり伝える。
  // 「下げてから開く」のままだと Jev が下げ続けて開かないことがある
  const atHeight = (z) => within(z - tcp.z);
  let aligned;
  if (s.holding) {
    const slot = freeTraySlot(s);
    const overSlot = aligned = within(slot.x - tcp.x) && within(slot.y - tcp.y);
    if (!overSlot && tcp.z < HOVER_Z - ALIGN_TOL) phase = `lift the held cube to the carry height (z=${HOVER_Z}) before moving sideways`;
    else if (!overSlot) phase = 'carry the held cube above the free tray slot';
    else if (atHeight(RELEASE_Z)) phase = 'OPEN NOW: the held cube is at the release height above the tray slot. Choose open.';
    else if (tcp.z > RELEASE_Z) phase = 'lower the held cube toward the release height (do not open yet)';
    else phase = 'too low: raise the held cube to the release height';
    goal = { x: slot.x, y: slot.y, z: overSlot ? RELEASE_Z : HOVER_Z };
  } else {
    const c = s.cubes_cm[targetCube];
    const overCube = aligned = within(c.x - tcp.x) && within(c.y - tcp.y);
    if (!gripperOpen) phase = 'open the gripper';
    else if (!overCube && tcp.z < HOVER_Z - ALIGN_TOL) phase = `raise the gripper to the travel height (z=${HOVER_Z}) before moving sideways`;
    else if (!overCube) phase = `move above the ${targetCube} cube`;
    else if (atHeight(GRASP_Z)) phase = `CLOSE NOW: the open gripper is around the ${targetCube} cube. Choose close.`;
    else if (tcp.z > GRASP_Z) phase = `descend onto the ${targetCube} cube (do not close yet)`;
    else phase = `too low: raise the gripper to the ${targetCube} cube's grasp height`;
    goal = { x: c.x, y: c.y, z: overCube ? GRASP_Z : HOVER_Z };
  }
  // 許容範囲内の誤差は 0 として渡す。残りの 0.2cm を 0.5cm 刻みで直そうとして
  // 前後に往復し続けるのを防ぐ
  if (aligned) goal = { ...goal, x: tcp.x, y: tcp.y };
  const dz = goal.z - tcp.z;
  return {
    phase,
    aligned_above_goal: aligned,
    goal_cm: goal,
    // goal - 現在の手先（許容範囲内は 0）
    delta_cm: { dx: round1(goal.x - tcp.x), dy: round1(goal.y - tcp.y), dz: within(dz) ? 0 : round1(dz) },
  };
}

function remainingCubes(s) {
  return Object.keys(s.cubes_cm).filter((n) => !s.in_tray.includes(n));
}

// ---------------------------------------------------------------------------
// Jev
// ---------------------------------------------------------------------------

async function askJev(state, questions) {
  const res = await fetch(JEV_API_URL, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${JEV_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: JEV_MODEL, state, questions }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    const error = new Error(`Jev API error ${res.status}: ${text}`);
    error.status = res.status;
    throw error;
  }
  return (await res.json()).answers;
}

// 今の状況で選んでよい手。プロンプトの指示だけでは守られないことがあるので、
// 選択肢そのものから外して物理的に選べなくする
function allowedActions(s, task) {
  const low = s.tcp_cm.z < HOVER_Z - ALIGN_TOL - 1e-6;
  const aligned = task.aligned_above_goal;
  const allowed = Object.keys(ACTIONS).filter((k) => {
    if (/^(forward|back|left|right)_/.test(k)) return !aligned && !low;   // 低いまま横に動かない（引きずり防止）
    if (k.startsWith('down_')) return aligned;                             // 目標の真上でだけ下げる
    if (k === 'close') return !s.holding && aligned;                       // キューブの真上でだけ掴む
    if (k === 'open') return !s.holding || aligned;                        // トレイの真上でだけ離す
    return true;
  });
  return allowed.length ? allowed : Object.keys(ACTIONS);
}

function buildQuestions(s, remaining, task) {
  const allowed = allowedActions(s, task);
  const questions = {
    action: {
      type: 'choice',
      instructions:
        'You control a SO-101 robot arm gripper. Choose the single best next action to reach task.goal_cm ' +
        'and complete task.phase. task.delta_cm = goal - current gripper position (cm). ' +
        'Reduce the largest horizontal error first with 2 cm moves, then 0.5 cm moves. ' +
        'When task.aligned_above_goal is true (dx and dy are 0), the gripper is already directly above the goal: ' +
        'do NOT move forward/back/left/right any more; only move up/down or open/close. ' +
        'Never lower the gripper unless it is directly above the goal. ' +
        'If task.phase starts with OPEN NOW choose open; if it starts with CLOSE NOW choose close. ' +
        'If lastResult contains ERROR, choose a different action.',
      criteria: Object.fromEntries(allowed.map((k) => [k, ACTIONS[k].desc])),
    },
  };
  // 何も持っていないときだけ、次に運ぶキューブを選ばせる
  if (!s.holding) {
    questions.target = {
      type: 'choice',
      instructions: 'Which cube should be picked up and carried to the tray next? Prefer the cube closest to the gripper.',
      criteria: Object.fromEntries(remaining.map((n) => {
        const c = s.cubes_cm[n];
        const d = Math.hypot(c.x - s.tcp_cm.x, c.y - s.tcp_cm.y);
        return [n, `The ${n} cube at x=${c.x}, y=${c.y} cm, ${round1(d)} cm from the gripper`];
      })),
    };
  }
  return questions;
}

// JEV_MOCK=1 用: Jev と同じ形の答えを簡易ルールで作る
function mockAnswers(state, questions) {
  const pick = (choice, keys) => ({
    type: 'choice', choice, confidence: 1,
    probabilities: Object.fromEntries(keys.map((k) => [k, k === choice ? 1 : 0])),
  });
  const answers = {};
  if (questions.target) {
    const keys = Object.keys(questions.target.criteria);
    const t = state.tcp_cm;
    const nearest = keys.sort((a, b) =>
      Math.hypot(state.cubes_cm[a].x - t.x, state.cubes_cm[a].y - t.y) -
      Math.hypot(state.cubes_cm[b].x - t.x, state.cubes_cm[b].y - t.y))[0];
    answers.target = pick(nearest, Object.keys(questions.target.criteria));
  }
  const { dx, dy, dz } = state.task.delta_cm;
  const xMove = Math.abs(dx) >= 2 ? (dx > 0 ? 'forward_2cm' : 'back_2cm') : (dx > 0 ? 'forward_05cm' : 'back_05cm');
  const yMove = Math.abs(dy) >= 2 ? (dy > 0 ? 'left_2cm' : 'right_2cm') : (dy > 0 ? 'left_05cm' : 'right_05cm');
  // 候補を良い順に並べ、直前にエラーになった手は避ける
  const candidates = [];
  if (state.task.phase === 'open the gripper') candidates.push('open');
  else if (Math.abs(dx) > 0.3 || Math.abs(dy) > 0.3) {
    if (dz > 1) candidates.push('up_2cm');
    const xFirst = Math.abs(dx) >= Math.abs(dy);
    if (Math.abs(dx) > 0.3 && xFirst) candidates.push(xMove);
    if (Math.abs(dy) > 0.3) candidates.push(yMove);
    if (Math.abs(dx) > 0.3 && !xFirst) candidates.push(xMove);
  } else if (dz <= -2) candidates.push('down_2cm');
  else if (dz < -0.2) candidates.push('down_05cm');
  else if (dz > 1) candidates.push('up_2cm');
  else candidates.push(state.holding ? 'open' : 'close');
  const failed = String(state.lastResult || '').startsWith('ERROR') ? state.lastAction : null;
  const allowed = Object.keys(questions.action.criteria);
  const ok = candidates.filter((c) => allowed.includes(c));
  const a = ok.find((c) => c !== failed) || ok[0] || (allowed.includes('up_2cm') ? 'up_2cm' : allowed[0]);
  answers.action = pick(a, allowed);
  return answers;
}

// ---------------------------------------------------------------------------
// エージェントループ
// ---------------------------------------------------------------------------

const agent = {
  running: false, done: false, steps: 0, target: null,
  lastDecision: null, lastResult: null, lastError: null, log: [],
};

function agentInfo() {
  return {
    model: JEV_MODEL, mock: MOCK, running: agent.running, done: agent.done, steps: agent.steps,
    lastDecision: agent.lastDecision, lastError: agent.lastError, log: agent.log.slice(-20),
  };
}
function publishAgent() { sendEvent('agent', agentInfo()); }

function agentLog(entry) {
  agent.log.push({ time: new Date().toISOString(), ...entry });
  if (agent.log.length > 100) agent.log.shift();
  console.log('[jev]', JSON.stringify(entry));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function agentTick() {
  const s = simState;
  const remaining = remainingCubes(s);
  if (!s.holding && !remaining.includes(agent.target)) agent.target = null;

  // target を選び直すかどうかに関わらず、状態は「今の狙い」を基準に作る
  const provisional = agent.target || remaining[0];
  const task = describeTask(s, provisional);
  const questions = buildQuestions(s, remaining, task);
  const state = {
    task: {
      goal: 'Pick up every cube and put it in the tray, one at a time.',
      ...task,
      target_cube: s.holding || provisional,
      carry_height_cm: HOVER_Z,
    },
    coordinateSystem: 'cm. Origin = robot base. +x forward, +y left, +z up. Cubes are 2.5 cm; a cube center on the table is z=1.25.',
    tcp_cm: s.tcp_cm,
    gripper_open_percent: s.joints.gripper,
    holding: s.holding,
    cubes_cm: s.cubes_cm,
    tray_cm: s.tray_cm,
    in_tray: s.in_tray,
    lastAction: agent.lastDecision?.action ?? null,
    lastResult: agent.lastResult,
  };

  // 選べる手が1つしかなく、キューブ選びも不要なら Jev に聞かずにその手を実行する
  const only = Object.keys(questions.action.criteria);
  const forced = only.length === 1 && !questions.target;
  const answers = forced
    ? { action: { type: 'choice', choice: only[0], probabilities: { [only[0]]: 1 }, confidence: null } }
    : MOCK ? mockAnswers(state, questions) : await askJev(state, questions);

  // Jev が別のキューブを選んだら、そのキューブ基準で目標を作り直してから一手を選ばせる
  if (answers.target && answers.target.choice !== provisional && remaining.includes(answers.target.choice)) {
    agent.target = answers.target.choice;
    agent.steps++;   // 狙いの切り替えも1手と数える（選び直しが続いても MAX_STEPS で止まる）
    agentLog({ step: agent.steps, retarget: agent.target });
    return;
  }
  if (answers.target) agent.target = answers.target.choice;

  const action = answers.action.choice;
  agent.steps++;
  const cmd = ACTIONS[action]?.cmd;
  if (!cmd) {
    agent.lastResult = `ERROR: unknown action ${action}`;
    agentLog({ step: agent.steps, error: agent.lastResult });
    return;
  }
  const result = await runOnSim(cmd);
  agent.lastResult = result;
  agent.lastDecision = {
    target: state.task.target_cube,
    phase: state.task.phase,
    action,
    actionProbabilities: answers.action.probabilities,
    confidence: answers.action.confidence,
    forced,
    allowedActions: only,
    result,
  };
  agentLog({ step: agent.steps, target: state.task.target_cube, action, ...(forced && { forced }), result });
}

async function runAgent() {
  if (agent.running) return;
  if (!MOCK && !JEV_API_KEY) {
    agent.lastError = 'TYPESAFE_API_KEY が設定されていません';
    console.error(`[jev] ${agent.lastError}`);
    publishAgent();
    return;
  }
  Object.assign(agent, { running: true, done: false, steps: 0, target: null, lastError: null, lastResult: null });
  console.log(`[jev] エージェントを開始します${MOCK ? ' (MOCK)' : ''}`);
  publishAgent();

  let backoff = 1000;
  while (agent.running) {
    if (!simState || Date.now() - simStateAt > 3000) {
      agent.lastError = 'ブラウザが接続されていないため停止しました';
      break;
    }
    if (remainingCubes(simState).length === 0 && !simState.holding) {
      agent.done = true;
      console.log(`[jev] 全キューブをトレイに入れました！ (${agent.steps} steps)`);
      break;
    }
    if (agent.steps >= MAX_STEPS) {
      agent.lastError = `最大ステップ数 (${MAX_STEPS}) に達したため停止しました`;
      break;
    }
    try {
      await agentTick();
      backoff = 1000;
      publishAgent();
      // 結果の状態がブラウザから届くのを待つ
      await sleep(TICK_MS);
    } catch (error) {
      agent.lastError = error.message;
      console.error('[jev]', error.message);
      publishAgent();
      if (error.status === 401 || error.status === 422) break;
      // 429 / 529 / ネットワークエラーは指数バックオフで再試行
      await sleep(backoff);
      backoff = Math.min(backoff * 2, 30000);
    }
  }
  agent.running = false;
  publishAgent();
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

function readJson(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', (c) => { body += c; if (body.length > 1e6) req.destroy(); });
    req.on('end', () => { try { resolve(JSON.parse(body || '{}')); } catch { resolve({}); } });
  });
}
function json(res, code, data) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const route = `${req.method} ${url.pathname}`;

  if (route === 'GET /' || route === 'GET /index.html') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(fs.readFileSync(path.join(__dirname, 'index.html')));
  }

  if (route === 'GET /events') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive' });
    res.write(': connected\n\n');
    sseClients.add(res);
    sendEvent('agent', agentInfo(), res);
    const ping = setInterval(() => res.write(': ping\n\n'), 15000);
    req.on('close', () => { clearInterval(ping); sseClients.delete(res); });
    console.log(`ブラウザが接続しました (${sseClients.size})`);
    if (AUTOSTART) setTimeout(runAgent, 1500);
    return;
  }

  if (route === 'POST /api/state') {
    simState = await readJson(req);
    simStateAt = Date.now();
    return json(res, 200, { ok: true });
  }

  if (route === 'POST /api/result') {
    const { id, text, state } = await readJson(req);
    if (state) { simState = state; simStateAt = Date.now(); }
    pending.get(id)?.(text);
    pending.delete(id);
    return json(res, 200, { ok: true });
  }

  if (route === 'GET /api/state') return json(res, 200, { connected: sseClients.size > 0, state: simState });
  if (route === 'GET /api/agent') return json(res, 200, agentInfo());

  if (route === 'POST /api/agent/start') {
    if (!MOCK && !JEV_API_KEY) return json(res, 400, { error: 'TYPESAFE_API_KEY is not set' });
    runAgent();
    return json(res, 200, { running: true });
  }
  if (route === 'POST /api/agent/stop') {
    agent.running = false;
    publishAgent();
    return json(res, 200, { running: false });
  }

  // 任意のコマンドを実行（手動操作・デバッグ用）: {"cmd": "move_to 18 0 5"}
  if (route === 'POST /api/run') {
    const { cmd } = await readJson(req);
    if (!cmd) return json(res, 400, { error: 'cmd is required' });
    try { return json(res, 200, { result: await runOnSim(String(cmd)) }); }
    catch (e) { return json(res, 503, { error: e.message }); }
  }

  if (route === 'POST /api/reset') {
    agent.running = false;
    try { return json(res, 200, { result: await runOnSim(`reset ${url.searchParams.get('seed') ?? ''}`.trim()) }); }
    catch (e) { return json(res, 503, { error: e.message }); }
  }

  json(res, 404, { error: 'not found' });
});

server.listen(PORT, () => {
  console.log(`サーバーが起動しました: http://localhost:${PORT}`);
  console.log(`[jev] model=${JEV_MODEL} mock=${MOCK} tick=${TICK_MS}ms maxSteps=${MAX_STEPS} autostart=${AUTOSTART}`);
  if (!MOCK && !JEV_API_KEY) console.warn('[jev] TYPESAFE_API_KEY が未設定です（JEV_MOCK=1 なら APIキーなしで動作確認できます）');
});
