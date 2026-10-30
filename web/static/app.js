const loginPanel = document.getElementById('login-panel');
const homePanel = document.getElementById('home-panel');
const pwdPanel = document.getElementById('pwd-panel');
const pwdForm = document.getElementById('pwd-form');
const pwdMsg = document.getElementById('pwd-msg');
const loginForm = document.getElementById('login-form');
const loginMsg = document.getElementById('login-msg');
const btnLogin = document.getElementById('btn-login');

async function api(path, options) {
  const resp = await fetch(path, options);
  const data = await resp.json().catch(() => ({}));
  return { status: resp.status, data };
}

function setMsg(text, ok) {
  loginMsg.textContent = text || '';
  loginMsg.classList.toggle('ok', !!ok);
}

function showLogin(notice) {
  pwdPanel.classList.add('hidden');
  loginPanel.classList.remove('hidden');
  homePanel.classList.add('hidden');
  document.getElementById('main-nav').classList.add('hidden');
  if (notice) setMsg(notice, false);
}

function showPwd(forced) {
  loginPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
  document.getElementById('main-nav').classList.add('hidden');
  pwdPanel.classList.remove('hidden');
  document.getElementById('btn-pwd-back').classList.toggle('hidden', !!forced);
  document.getElementById('pwd-desc').textContent = forced
    ? '首次登录默认密码就是你的 QQ 号，请先设置一个新密码'
    : '修改网页密码需要先输入原密码';
  pwdMsg.textContent = '';
  pwdForm.reset();
}

function showHome(player) {
  pwdPanel.classList.add('hidden');
  loginPanel.classList.add('hidden');
  homePanel.classList.remove('hidden');
  document.getElementById('player-name').textContent = player.nick || `玩家${player.qq}`;
  document.getElementById('player-qq').textContent = `QQ ${player.qq}`;
  document.getElementById('stat-fish').textContent = player.fish;
  document.getElementById('stat-stone').textContent = player.eye_stones;
  document.getElementById('stat-cats').textContent = player.cats;
  document.getElementById('stat-summon').textContent = player.summon_count;
  document.getElementById('stat-signin').textContent = player.signin_total;
  // 「管理」导航页只有管理员可见；普通玩家即使上次停在管理页也要退回远征页
  document.getElementById('nav-admin').classList.toggle('hidden', !player.is_admin);
  if (!player.is_admin && currentTab === 'admin') currentTab = 'expedition';
  afterShowHome();
}

async function refresh() {
  const { status, data } = await api('/api/me');
  if (status === 200 && data.ok) {
    if (data.player.must_change_pwd) showPwd(true);
    else showHome(data.player);
  } else {
    showLogin();
  }
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  btnLogin.disabled = true;
  setMsg('登录中…', false);
  const { status, data } = await api('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      qq: document.getElementById('input-qq').value.trim(),
      password: document.getElementById('input-pwd').value,
    }),
  });
  btnLogin.disabled = false;
  if (status === 200 && data.ok) {
    document.getElementById('input-pwd').value = '';
    setMsg('');
    if (data.player.must_change_pwd) showPwd(true);
    else showHome(data.player);
  } else {
    setMsg(data.msg || '登录失败喵', false);
  }
});

document.getElementById('btn-logout').addEventListener('click', async () => {
  await api('/api/logout', { method: 'POST' });
  document.getElementById('input-pwd').value = '';
  showLogin('已登出喵');
});

document.getElementById('btn-change-pwd').addEventListener('click', () => showPwd(false));
document.getElementById('btn-pwd-back').addEventListener('click', () => refresh());

pwdForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const oldPwd = document.getElementById('pwd-old').value;
  const newPwd = document.getElementById('pwd-new').value;
  const newPwd2 = document.getElementById('pwd-new2').value;
  if (newPwd !== newPwd2) {
    pwdMsg.textContent = '两次输入的新密码不一致喵';
    return;
  }
  pwdMsg.textContent = '提交中…';
  const { status, data } = await api('/api/change_password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old: oldPwd, new: newPwd }),
  });
  if (status === 200 && data.ok) {
    pwdForm.reset();
    pwdMsg.textContent = '';
    await refresh();
  } else {
    pwdMsg.textContent = data.msg || '修改失败喵';
  }
});

refresh();

// ==================== Farkle 网页版 ====================

const fkPanel = document.getElementById('farkle-panel');
const fkLobby = document.getElementById('fk-lobby');
const fkRoom = document.getElementById('fk-room');
const fkRooms = document.getElementById('fk-rooms');
const fkLobbyMsg = document.getElementById('fk-lobby-msg');
const fkToast = document.getElementById('fk-toast');

const PIPS = {
  1: [4], 2: [0, 8], 3: [0, 4, 8],
  4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8],
};

let fkCode = null;
let fkState = null;
let fkSig = null;
let fkHandSig = null;
let fkLastPhase = null;
let fkSelected = new Set();
let fkLobbyTimer = null;
let fkRoomTimer = null;
let fkToastTimer = null;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function fkMsg(text, ok) {
  fkToast.textContent = text || '';
  fkToast.classList.toggle('ok', !!ok);
  clearTimeout(fkToastTimer);
  if (text) fkToastTimer = setTimeout(() => { fkToast.textContent = ''; }, 4000);
}

function fmtOpen(bid) {
  const v = -bid;
  return (v >= 0 ? '+' : '') + v;
}

function dieEl(die, opts) {
  opts = opts || {};
  const el = document.createElement('div');
  el.className = 'die' + (opts.small ? ' small' : '')
    + (opts.selectable ? ' selectable' : '') + (opts.selected ? ' sel' : '');
  el.style.background = die.fill;
  el.style.borderColor = die.outline;
  if (die.kind === 'd20' && die.raw) {
    el.classList.add('d20');
    el.style.display = 'flex';
    el.style.flexDirection = 'column';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    const big = document.createElement('span');
    big.className = 'd20-face';
    big.textContent = String(die.raw);
    el.appendChild(big);
    if (die.value) {
      const sub = document.createElement('span');
      sub.className = 'd20-sub';
      sub.textContent = '=' + die.value;
      el.appendChild(sub);
    }
    return el;
  }
  if (die.wild || !die.value) {
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    const span = document.createElement('span');
    span.className = die.wild ? 'wild' : 'blank';
    span.textContent = die.wild ? '万' : '?';
    el.appendChild(span);
    return el;
  }
  const lit = new Set(PIPS[die.value] || []);
  for (let i = 0; i < 9; i++) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    if (lit.has(i)) {
      const pip = document.createElement('span');
      pip.className = 'pip';
      cell.appendChild(pip);
    }
    el.appendChild(cell);
  }
  return el;
}

function fkToggle(id, show) {
  document.getElementById(id).classList.toggle('hidden', !show);
}

async function enterFarkle() {
  loginPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
  pwdPanel.classList.add('hidden');
  fkPanel.classList.remove('hidden');
  fkLobby.classList.remove('hidden');
  fkRoom.classList.add('hidden');
  fkCode = null;
  fkLobbyMsg.textContent = '';
  loadLoadouts();
  const { status, data } = await api('/api/farkle/mine');
  if (status === 401) { fkPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 200 && data.ok && data.code) { enterRoom(data.code); return; }
  await refreshRooms();
  loadBotRank();
  loadDumbWeek();
  clearInterval(fkRoomTimer);
  fkLobbyTimer = setInterval(refreshRooms, 2500);
}

function backToLobby() {
  clearInterval(fkRoomTimer);
  fkRoomTimer = null;
  fkCode = null;
  fkLastPhase = null;
  hideChat('fk');
  fkRoom.classList.add('hidden');
  fkLobby.classList.remove('hidden');
  refreshRooms();
  loadBotRank();
  loadDumbWeek();
  clearInterval(fkLobbyTimer);
  fkLobbyTimer = setInterval(refreshRooms, 2500);
}

async function refreshRooms() {
  const { status, data } = await api('/api/farkle/rooms');
  if (status === 401) { clearInterval(fkLobbyTimer); fkPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  fkRooms.innerHTML = '';
  if (!data.rooms.length) {
    const p = document.createElement('p');
    p.className = 'room-empty';
    p.textContent = '还没有房间，创建一个等对手来吧';
    fkRooms.appendChild(p);
    return;
  }
  data.rooms.forEach((r) => {
    const row = document.createElement('div');
    row.className = 'room-row';
    const ongoing = r.phase !== 'waiting';
    const meta = document.createElement('div');
    meta.className = 'room-meta';
    meta.innerHTML = (ongoing ? '<span class="room-stone">对局中</span> · ' : '')
      + (r.bot ? `${esc(r.bot_name || '人机局')} · ` : '')
      + `目标 ${r.target} 分 · `
      + (r.stones > 0 ? `<span class="room-stone">猫眼石 ${r.stones}</span>` : '普通局')
      + ` · 房间号 ${esc(r.code)}`;
    const host = document.createElement('div');
    host.className = 'room-host';
    host.textContent = ongoing ? (r.players || []).join(' vs ') : r.host;
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary btn-sm';
    btn.textContent = ongoing ? '观战' : '加入';
    btn.addEventListener('click', () => (ongoing ? spectateRoom(r.code) : joinRoom(r.code)));
    row.appendChild(host);
    row.appendChild(meta);
    row.appendChild(btn);
    fkRooms.appendChild(row);
  });
}

async function createRoom() {
  fkLobbyMsg.textContent = '';
  const target = document.getElementById('fk-target').value;
  const on = document.getElementById('fk-stones-on').checked;
  const stones = on ? document.getElementById('fk-stones').value : 0;
  const { status, data } = await api('/api/farkle/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target: target, stones: stones }),
  });
  if (status === 200 && data.ok) enterRoom(data.code);
  else fkLobbyMsg.textContent = data.msg || '创建失败喵';
}

async function startBotGame(dumb = false) {
  const msg = document.getElementById(dumb ? 'fk-dumb-msg' : 'fk-bot-msg');
  const target = dumb ? 4000 : document.getElementById('fk-bot-target').value;
  const stones = dumb ? 0 : document.getElementById('fk-bot-stones').value;
  msg.textContent = '';
  const { status, data } = await api('/api/farkle/bot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target: target, stones: stones, dumb: dumb }),
  });
  if (status === 200 && data.ok) enterRoom(data.code);
  else msg.textContent = data.msg || '开局失败喵';
}

async function loadLoadouts() {
  const box = document.getElementById('fk-loadouts');
  const { status, data } = await api('/api/farkle/loadouts');
  if (status !== 200 || !data.ok) return;
  box.innerHTML = data.loadouts.map((l) => {
    const parts = String(l.desc || '').split('｜');
    const comp = parts[0] || '';
    const effect = parts[1] || '无特效，与普通骰一致';
    return `<div class="loadout-row">
      <span class="loadout-name">${esc(comp)}</span>
      <span class="loadout-desc">${esc(effect)}</span>
    </div>`;
  }).join('');
}

async function loadBotRank() {
  const box = document.getElementById('fk-bot-rank');
  const { status, data } = await api('/api/farkle/bot_rank');
  if (status === 401) { fkPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  const rows = data.rows.map((r, i) => `
    <div class="rank-row">
      <span class="rank-no">${i + 1}</span>
      <span class="rank-name">${esc(r.name)}</span>
      <span class="rank-val">${r.wins} 胜 ${r.losses} 负</span>
      <span class="rank-reward">胜率 ${(r.rate * 100).toFixed(1)}% · 净 ${r.net > 0 ? '+' : ''}${r.net}</span>
    </div>`).join('');
  const mine = data.mine
    ? `<p class="hint">你的战绩：${data.mine.wins} 胜 ${data.mine.losses} 负（胜率 ${(data.mine.rate * 100).toFixed(1)}%）· 净 ${data.mine.net > 0 ? '+' : ''}${data.mine.net} 猫眼石</p>`
    : '<p class="hint">你还没有对战记录，挑战一次机器人吧</p>';
  box.innerHTML = (rows || '<p class="room-empty">还没有人对战过机器人喵</p>') + mine;
}

async function loadDumbWeek() {
  const box = document.getElementById('fk-dumb-week');
  const { status, data } = await api('/api/farkle/dumb_week');
  if (status === 401) { fkPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  document.getElementById('fk-dumb-week-sub').textContent =
    `本周（${data.week}）· 排行依据：${data.basis} · 满 ${data.min_games} 局才领奖 · 周三 00:00 刷新`;
  const rows = data.rows.map((r) => `
    <div class="rank-row">
      <span class="rank-no">${r.rank}</span>
      <span class="rank-name">${esc(r.name)}</span>
      <span class="rank-val">${r.wins} 胜 ${r.losses} 负（${r.games} 局）· 胜率 ${(r.rate * 100).toFixed(1)}%</span>
      <span class="rank-reward">奖励 ${r.reward} 鱼干</span>
    </div>`).join('');
  const restRows = (data.rest || []).map((r) => `
    <div class="rank-row">
      <span class="rank-no">—</span>
      <span class="rank-name">${esc(r.name)}</span>
      <span class="rank-val">${r.wins} 胜 ${r.losses} 负（${r.games} 局）· 胜率 ${(r.rate * 100).toFixed(1)}%</span>
      <span class="rank-reward">不满 ${data.min_games} 局，不领奖</span>
    </div>`).join('');
  const restBlock = restRows
    ? `<p class="hint">本周不满 ${data.min_games} 局（不参与领奖）</p>${restRows}`
    : '';
  const mine = data.mine
    ? `<p class="hint">你对${data.name}：${data.mine.wins} 胜 ${data.mine.losses} 负（${data.mine.games} 局）`
      + `${data.mine.left > 0 ? `，还差 ${data.mine.left} 局上榜` : '，已上榜'}</p>`
    : `<p class="hint">你本周还没和${data.name}对战过，挑战一次吧</p>`;
  const note = `<p class="hint">每周按胜率排名发鱼干：第1名 ${data.rewards[0]}，逐名 -100，`
    + `发到第 ${data.rewards.length} 名 ${data.rewards[data.rewards.length - 1]}；同分并列领同一档</p>`;
  const empty = `<p class="room-empty">本周还没有人打满 ${data.min_games} 局，去挑战吧</p>`;
  box.innerHTML = (rows || empty) + restBlock + mine + note;
}

document.getElementById('btn-fk-bot').addEventListener('click', () => startBotGame(false));
document.getElementById('btn-fk-dumb').addEventListener('click', () => startBotGame(true));
document.getElementById('btn-fk-bot-rank').addEventListener('click', loadBotRank);
document.getElementById('btn-fk-dumb-week').addEventListener('click', loadDumbWeek);

async function joinRoom(code) {
  fkLobbyMsg.textContent = '';
  const { status, data } = await api('/api/farkle/join', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  });
  if (status === 200 && data.ok) enterRoom(data.code);
  else fkLobbyMsg.textContent = data.msg || '加入失败喵';
}

function spectateRoom(code) {
  // 观战不加入对局，直接进入只读视图
  fkLobbyMsg.textContent = '';
  enterRoom(code);
}

async function cancelRoom() {
  if (!fkCode) return;
  const { status, data } = await api('/api/farkle/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: fkCode }),
  });
  if (status === 200 && data.ok) backToLobby();
  else fkMsg(data.msg || '取消失败喵');
}

async function fkAct(action, extra) {
  if (!fkCode) return;
  const body = Object.assign({ code: fkCode, action: action }, extra || {});
  const { status, data } = await api('/api/farkle/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (status === 200 && data.ok) {
    fkSig = fkSignature(data.room);
    renderRoom(data.room);
  } else {
    fkMsg(data.msg || '操作失败喵');
  }
}

function fkSignature(r) {
  return JSON.stringify([
    r.phase, r.turn, r.auction,
    r.players.map((p) => p.total),
    r.hand.map((d) => d.kind + ':' + d.value),
    r.locked.map((d) => d.kind + ':' + d.value),
    r.turn_score, r.winner, r.log.length,
  ]);
}

async function enterRoom(code) {
  clearInterval(fkLobbyTimer);
  fkLobbyTimer = null;
  fkCode = code;
  fkState = null;
  fkSig = null;
  fkHandSig = null;
  fkSelected = new Set();
  fkLobby.classList.add('hidden');
  fkRoom.classList.remove('hidden');
  showChat('fk');
  buildRoomDom();
  await pollRoom();
  clearInterval(fkRoomTimer);
  fkRoomTimer = setInterval(pollRoom, 1200);
}

async function pollRoom() {
  const code = fkCode;
  if (!code) return;
  const { status, data } = await api('/api/farkle/state?code=' + encodeURIComponent(code));
  if (code !== fkCode) return;   // 已离开或换了房间，丢弃旧响应
  if (status === 401) { clearInterval(fkRoomTimer); fkPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 404) {
    fkMsg('房间已结束喵');
    backToLobby();
    return;
  }
  if (status !== 200 || !data.ok) return;
  const s = fkSignature(data.room);
  if (s !== fkSig) {
    fkSig = s;
    renderRoom(data.room);
  }
  renderChat('fk', data.room.chat);
}

function buildRoomDom() {
  fkRoom.innerHTML = `
    <div class="card fk-head">
      <div class="fk-head-top">
        <div class="fk-title">Farkle · 目标 <span id="fk-target-show"></span> 分<span id="fk-stones-show"></span></div>
        <div class="fk-head-right">
          <div class="fk-code">房间号 <b id="fk-code-show"></b></div>
          <div id="fk-spectate-badge" class="fk-spectate hidden">观战中</div>
        </div>
      </div>
      <div id="fk-players" class="fk-players"></div>
    </div>

    <div id="fk-waiting" class="card fk-card hidden">
      <div class="fk-info">等待另一位玩家加入……把房间号 <b id="fk-wait-code"></b> 发给对手即可</div>
      <div class="actions"><button id="fk-cancel" class="btn btn-ghost btn-sm">解散房间</button></div>
    </div>

    <div id="fk-auction" class="card fk-card hidden">
      <div class="panel-title">先手拍卖</div>
      <div id="fk-seat" class="fk-seat"></div>
      <div id="fk-auction-info" class="fk-info"></div>
      <div id="fk-auction-actions" class="actions">
        <input id="fk-bid-input" type="number" step="50" placeholder="出价（50 的倍数，可为负）">
        <button id="fk-bid" class="btn btn-primary btn-sm">出价</button>
        <button id="fk-accept" class="btn btn-ghost btn-sm">接受</button>
        <span id="fk-auction-hint" class="hint"></span>
      </div>
    </div>

    <div id="fk-table" class="card fk-card hidden">
      <div class="fk-table-top">
        <div id="fk-turn-label" class="fk-turn"></div>
        <div id="fk-score" class="fk-score"></div>
      </div>
      <div id="fk-locked-label" class="locked-label hidden">已锁定</div>
      <div id="fk-locked" class="dice-row locked"></div>
      <div id="fk-hand" class="dice-row"></div>
      <div id="fk-table-actions" class="actions">
        <button id="fk-lock" class="btn btn-primary btn-sm">锁定选中</button>
        <button id="fk-roll" class="btn btn-ghost btn-sm">继续掷</button>
        <button id="fk-bank" class="btn btn-ghost btn-sm">入账</button>
        <span id="fk-table-hint" class="hint"></span>
      </div>
    </div>

    <div id="fk-result" class="card fk-result hidden"></div>

    <div class="card fk-card">
      <div class="panel-title">对局记录</div>
      <div id="fk-log" class="log"></div>
    </div>

    <div class="actions">
      <button id="fk-surrender" class="btn btn-ghost btn-sm">投降</button>
      <button id="fk-back-lobby" class="btn btn-ghost btn-sm">返回大厅</button>
    </div>`;

  document.getElementById('fk-bid').addEventListener('click', () => {
    const el = document.getElementById('fk-bid-input');
    const v = el.value.trim();
    // 留空 = 交给后端按「对方出价 + 50」补默认值
    fkAct('bid', { value: v });
    if (v === '') { delete el.dataset.forBid; }
  });
  document.getElementById('fk-accept').addEventListener('click', () => fkAct('accept'));
  document.getElementById('fk-lock').addEventListener('click', () => {
    if (!fkSelected.size) { fkMsg('先点选要锁定的骰子喵'); return; }
    fkAct('lock', { indices: Array.from(fkSelected) });
  });
  document.getElementById('fk-roll').addEventListener('click', () => fkAct('roll'));
  document.getElementById('fk-bank').addEventListener('click', () => fkAct('bank'));
  document.getElementById('fk-surrender').addEventListener('click', () => {
    if (window.confirm('确定投降吗？对方将直接获胜喵')) fkAct('surrender');
  });
  document.getElementById('fk-cancel').addEventListener('click', cancelRoom);
  document.getElementById('fk-back-lobby').addEventListener('click', backToLobby);
}

function renderRoom(state) {
  fkState = state;
  document.getElementById('fk-target-show').textContent = state.target;
  document.getElementById('fk-stones-show').textContent = state.stones > 0 ? ` · 猫眼石 ${state.stones}` : '';
  document.getElementById('fk-code-show').textContent = state.code;
  const waitCode = document.getElementById('fk-wait-code');
  if (waitCode) waitCode.textContent = state.code;

  const handSig = state.hand.map((d) => d.kind + ':' + d.value).join(',');
  if (handSig !== fkHandSig) { fkHandSig = handSig; fkSelected = new Set(); }

  renderPlayers(state);

  const isWaiting = state.phase === 'waiting';
  const isAuction = state.phase === 'auction';
  const isPlay = state.phase === 'keep' || state.phase === 'decide';
  const isOver = state.phase === 'finished';

  fkToggle('fk-waiting', isWaiting);
  fkToggle('fk-auction', isAuction);
  fkToggle('fk-table', isPlay);
  fkToggle('fk-result', isOver);

  // 观战者：只读，隐藏所有操作入口
  const spectator = !state.is_player;
  document.getElementById('fk-spectate-badge').classList.toggle('hidden', !spectator);
  document.getElementById('fk-auction-actions').classList.toggle('hidden', spectator);
  document.getElementById('fk-table-actions').classList.toggle('hidden', spectator);
  document.getElementById('fk-surrender').classList.toggle('hidden', isWaiting || isOver || spectator);
  if (isWaiting) {
    document.getElementById('fk-cancel').classList.toggle('hidden', state.my_index !== 0);
  }
  if (isAuction) renderAuction(state);
  if (isPlay) renderTable(state);
  if (isOver) renderResult(state);
  if (isOver && fkLastPhase !== 'finished') loadDumbWeek();
  fkLastPhase = state.phase;
  renderLog(state);
}

function renderPlayers(state) {
  const wrap = document.getElementById('fk-players');
  wrap.innerHTML = '';
  state.players.forEach((p, i) => {
    const div = document.createElement('div');
    div.className = 'fk-player'
      + (i === state.turn && state.phase !== 'finished' && state.phase !== 'auction' ? ' active' : '')
      + (i === state.my_index ? ' you' : '');
    div.innerHTML = `<div class="pname">${esc(p.name)}${i === state.my_index ? '（你）' : ''}</div>`
      + `<div class="pmeta">骰组：${esc(p.dice_desc)}</div>`
      + `<div class="ptotal">${p.total} 分</div>`;
    wrap.appendChild(div);
  });
}

function renderAuction(state) {
  const au = state.auction || {};
  const seat = document.getElementById('fk-seat');
  seat.innerHTML = '';
  (state.seat || []).forEach((desc, i) => {
    const d = document.createElement('div');
    d.textContent = (i === 0 ? '先手位：' : '后手位：') + desc;
    seat.appendChild(d);
  });

  const curIdx = au.turn;
  const cur = state.players[curIdx] || {};
  const holder = au.holder != null ? state.players[au.holder] : null;
  const info = document.getElementById('fk-auction-info');
  if (au.bid == null) {
    info.innerHTML = `<b>${esc(cur.name)}</b> 先出价：出价越高的越有资格拿先手`;
  } else {
    info.innerHTML = `当前最高出价 <b>${au.bid}</b>（<b>${esc(holder.name)}</b> 若成交即先手，`
      + `以 <b>${fmtOpen(au.bid)}</b> 分开局）；接受方为后手、0 分开局`;
  }

  const mine = state.my_index >= 0 && state.my_index === curIdx;
  const bidInput = document.getElementById('fk-bid-input');
  bidInput.disabled = !mine;
  document.getElementById('fk-bid').disabled = !mine;
  document.getElementById('fk-accept').disabled = !mine || au.bid == null;
  // 默认出价 = 对方出价 + 50：轮到本人且对方出价变化时自动填好，直接点「出价」即可
  if (mine && au.bid != null && bidInput.dataset.forBid !== String(au.bid)) {
    bidInput.value = au.bid + 50;
    bidInput.dataset.forBid = String(au.bid);
  }
  document.getElementById('fk-auction-hint').textContent = mine
    ? (au.bid == null
        ? '正数 = 拿先手但以该负分开局；负数 = 拿先手反而以正分开局'
        : `出价高于当前最高出价；留空直接「出价」= 默认加到 ${au.bid + 50}；或点「接受」让出先手`)
    : '等待对方出价……';
}

function renderTable(state) {
  const p = state.players[state.turn] || {};
  const myTurn = state.is_turn;
  const label = document.getElementById('fk-turn-label');
  if (state.phase === 'keep') {
    label.textContent = myTurn ? '轮到你：点选计分骰后锁定' : `${p.name} 正在锁定骰子……`;
  } else {
    label.textContent = myTurn ? '轮到你：继续掷 或 入账' : `${p.name} 正在决定……`;
  }
  label.classList.toggle('waiting', !myTurn);
  document.getElementById('fk-score').textContent = `本回合 ${state.turn_score} 分`;

  const lockedWrap = document.getElementById('fk-locked');
  lockedWrap.innerHTML = '';
  document.getElementById('fk-locked-label').classList.toggle('hidden', !state.locked.length);
  state.locked.forEach((d) => lockedWrap.appendChild(dieEl(d, { small: true })));

  const canSelect = state.phase === 'keep' && myTurn;
  const handWrap = document.getElementById('fk-hand');
  handWrap.innerHTML = '';
  state.hand.forEach((d, i) => {
    const el = dieEl(d, { selectable: canSelect, selected: fkSelected.has(i) });
    if (canSelect) {
      el.addEventListener('click', () => {
        if (fkSelected.has(i)) fkSelected.delete(i);
        else fkSelected.add(i);
        renderRoom(fkState);
      });
    }
    handWrap.appendChild(el);
  });

  const isKeep = state.phase === 'keep';
  const isDecide = state.phase === 'decide';
  const canBank = isDecide && state.can_bank !== false;
  const lockBtn = document.getElementById('fk-lock');
  const rollBtn = document.getElementById('fk-roll');
  const bankBtn = document.getElementById('fk-bank');
  lockBtn.classList.toggle('hidden', !isKeep);
  rollBtn.classList.toggle('hidden', !isDecide);
  bankBtn.classList.toggle('hidden', !canBank);
  lockBtn.disabled = !myTurn || !fkSelected.size;
  rollBtn.disabled = !myTurn;
  bankBtn.disabled = !myTurn || !canBank;
  document.getElementById('fk-table-hint').textContent = myTurn
    ? (isKeep ? '选中后点「锁定选中」'
      : (isDecide && !canBank ? '赌怪骰还在桌上，必须先锁定它才能入账'
        : '掷有爆骰风险，入账则收下本回合分'))
    : '等待对方行动……';
}

function renderResult(state) {
  const winner = state.players.find((p) => p.qq === state.winner);
  const lines = [`🏆 ${winner ? winner.name : '?'} 获胜！`];
  state.players.forEach((p) => lines.push(`${p.name}：${p.total} 分`));
  (state.settle_lines || []).forEach((l) => lines.push(l));
  const box = document.getElementById('fk-result');
  box.innerHTML =
    '<div class="panel-title">对局结束</div>'
    + lines.map((l) => `<div class="line">${esc(l)}</div>`).join('')
    + rematchButton('fk', state.is_player);
  bindRematch(box, 'fk', rematchFk);
}

function renderLog(state) {
  const box = document.getElementById('fk-log');
  box.innerHTML = '';
  state.log.forEach((l) => {
    const d = document.createElement('div');
    d.textContent = l;
    box.appendChild(d);
  });
  box.scrollTop = box.scrollHeight;
}

document.getElementById('btn-farkle').addEventListener('click', enterFarkle);
document.getElementById('btn-fk-back').addEventListener('click', () => {
  closeGamePanels();
  refresh();
});
document.getElementById('fk-stones-on').addEventListener('change', (e) => {
  document.getElementById('fk-stones').disabled = !e.target.checked;
});
document.getElementById('btn-fk-create').addEventListener('click', createRoom);

// ==================== 快艇骰子 网页版 ====================

const yzPanel = document.getElementById('yahtzee-panel');
const yzLobby = document.getElementById('yz-lobby');
const yzRoom = document.getElementById('yz-room');
const yzRooms = document.getElementById('yz-rooms');
const yzLobbyMsg = document.getElementById('yz-lobby-msg');
const yzToast = document.getElementById('yz-toast');

const YZ_MAX_ROLL = 3;

let yzCode = null;
let yzState = null;
let yzSig = null;
let yzDiceSig = null;
let yzSelected = new Set();
let yzLobbyTimer = null;
let yzRoomTimer = null;
let yzToastTimer = null;

function yzMsg(text, ok) {
  yzToast.textContent = text || '';
  yzToast.classList.toggle('ok', !!ok);
  clearTimeout(yzToastTimer);
  if (text) yzToastTimer = setTimeout(() => { yzToast.textContent = ''; }, 4000);
}

async function enterYahtzee() {
  loginPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
  pwdPanel.classList.add('hidden');
  yzPanel.classList.remove('hidden');
  yzLobby.classList.remove('hidden');
  yzRoom.classList.add('hidden');
  yzCode = null;
  yzLobbyMsg.textContent = '';
  loadWeekly();
  const { status, data } = await api('/api/yahtzee/mine');
  if (status === 401) { yzPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 200 && data.ok && data.code) { enterYzRoom(data.code); return; }
  await refreshYzRooms();
  clearInterval(yzRoomTimer);
  yzRoomTimer = null;
  yzLobbyTimer = setInterval(refreshYzRooms, 2500);
}

function backToYzLobby() {
  clearInterval(yzRoomTimer);
  yzRoomTimer = null;
  yzCode = null;
  hideChat('yz');
  yzRoom.classList.add('hidden');
  yzLobby.classList.remove('hidden');
  refreshYzRooms();
  loadWeekly();
  clearInterval(yzLobbyTimer);
  yzLobbyTimer = setInterval(refreshYzRooms, 2500);
}

async function refreshYzRooms() {
  const { status, data } = await api('/api/yahtzee/rooms');
  if (status === 401) { clearInterval(yzLobbyTimer); yzPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  yzRooms.innerHTML = '';
  if (!data.rooms.length) {
    const p = document.createElement('p');
    p.className = 'room-empty';
    p.textContent = '还没有房间，创建一个等对手来吧';
    yzRooms.appendChild(p);
    return;
  }
  data.rooms.forEach((r) => {
    const row = document.createElement('div');
    row.className = 'room-row';
    const ongoing = r.phase !== 'waiting';
    const meta = document.createElement('div');
    meta.className = 'room-meta';
    meta.textContent = (ongoing ? '对局中 · ' : '') + `${r.count}/${r.max} 人` + ` · 房间号 ${r.code}`;
    const host = document.createElement('div');
    host.className = 'room-host';
    host.textContent = ongoing ? (r.players || []).join(' vs ') : r.host;
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary btn-sm';
    btn.textContent = ongoing ? '观战' : '加入';
    btn.addEventListener('click', () => (ongoing ? enterYzRoom(r.code) : joinYzRoom(r.code)));
    row.appendChild(host);
    row.appendChild(meta);
    row.appendChild(btn);
    yzRooms.appendChild(row);
  });
}

async function createYzRoom() {
  yzLobbyMsg.textContent = '';
  const { status, data } = await api('/api/yahtzee/create', { method: 'POST' });
  if (status === 200 && data.ok) enterYzRoom(data.code);
  else yzLobbyMsg.textContent = data.msg || '创建失败喵';
}

async function joinYzRoom(code) {
  yzLobbyMsg.textContent = '';
  const { status, data } = await api('/api/yahtzee/join', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  });
  if (status === 200 && data.ok) enterYzRoom(data.code);
  else yzLobbyMsg.textContent = data.msg || '加入失败喵';
}

async function cancelYzRoom() {
  if (!yzCode) return;
  const { status, data } = await api('/api/yahtzee/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: yzCode }),
  });
  if (status === 200 && data.ok) backToYzLobby();
  else yzMsg(data.msg || '取消失败喵');
}

async function yzAct(action, extra) {
  if (!yzCode) return;
  const body = Object.assign({ code: yzCode, action: action }, extra || {});
  const { status, data } = await api('/api/yahtzee/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (status === 200 && data.ok) {
    if (!data.room) { backToYzLobby(); yzMsg('对局已取消喵'); return; }
    yzSig = yzSignature(data.room);
    renderYzRoom(data.room);
  } else {
    yzMsg(data.msg || '操作失败喵');
  }
}

function yzSignature(r) {
  return JSON.stringify([
    r.phase, r.turn, r.roll, r.dice.map((d) => d.value),
    r.players.map((p) => [p.total, p.score]),
    r.winner, r.log.length,
  ]);
}

async function enterYzRoom(code) {
  clearInterval(yzLobbyTimer);
  yzLobbyTimer = null;
  yzCode = code;
  yzState = null;
  yzSig = null;
  yzDiceSig = null;
  yzSelected = new Set();
  yzLobby.classList.add('hidden');
  yzRoom.classList.remove('hidden');
  showChat('yz');
  buildYzRoomDom();
  await pollYzRoom();
  clearInterval(yzRoomTimer);
  yzRoomTimer = setInterval(pollYzRoom, 1200);
}

async function pollYzRoom() {
  const code = yzCode;
  if (!code) return;
  const { status, data } = await api('/api/yahtzee/state?code=' + encodeURIComponent(code));
  if (code !== yzCode) return;   // 已离开或换了房间，丢弃旧响应
  if (status === 401) { clearInterval(yzRoomTimer); yzPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 404) { yzMsg('房间已结束喵'); backToYzLobby(); return; }
  if (status !== 200 || !data.ok) return;
  const s = yzSignature(data.room);
  if (s !== yzSig) {
    yzSig = s;
    renderYzRoom(data.room);
  }
  renderChat('yz', data.room.chat);
}

function buildYzRoomDom() {
  yzRoom.innerHTML = `
    <div class="card fk-head">
      <div class="fk-head-top">
        <div class="fk-title">快艇骰子 · <span id="yz-progress"></span></div>
        <div class="fk-head-right">
          <div class="fk-code">房间号 <b id="yz-code-show"></b></div>
          <div id="yz-spectate-badge" class="fk-spectate hidden">观战中</div>
        </div>
      </div>
      <div id="yz-players" class="fk-players"></div>
    </div>

    <div id="yz-waiting" class="card fk-card hidden">
      <div class="fk-info">等待玩家加入……现在是 <b id="yz-count"></b> 人，把房间号 <b id="yz-wait-code"></b> 发给朋友即可（最多 4 人）</div>
      <div class="actions">
        <button id="yz-start" class="btn btn-primary btn-sm">开始对局</button>
        <button id="yz-cancel" class="btn btn-ghost btn-sm">解散房间</button>
      </div>
    </div>

    <div id="yz-play" class="card fk-card hidden">
      <div class="fk-table-top">
        <div id="yz-turn-label" class="fk-turn"></div>
        <div id="yz-roll-label" class="fk-turn"></div>
      </div>
      <div id="yz-dice" class="dice-row"></div>
      <div class="actions">
        <button id="yz-reroll" class="btn btn-primary btn-sm">重投选中</button>
        <span class="hint">点选要重投的骰子（最多 3 投），或直接在计分板点空格计分</span>
      </div>
      <div id="yz-table" class="yz-table-wrap"></div>
    </div>

    <div id="yz-result" class="card fk-result hidden"></div>

    <div class="card fk-card">
      <div class="panel-title">对局记录</div>
      <div id="yz-log" class="log"></div>
    </div>

    <div class="actions">
      <button id="yz-giveup" class="btn btn-ghost btn-sm">放弃本局</button>
      <button id="yz-back-lobby" class="btn btn-ghost btn-sm">返回大厅</button>
    </div>`;

  document.getElementById('yz-start').addEventListener('click', () => yzAct('start'));
  document.getElementById('yz-reroll').addEventListener('click', () => {
    if (!yzSelected.size) { yzMsg('先点选要重投的骰子喵'); return; }
    yzAct('reroll', { indices: Array.from(yzSelected) });
  });
  document.getElementById('yz-giveup').addEventListener('click', () => {
    if (window.confirm('确定放弃本局吗？剩余格子将按 0 分锁定喵')) yzAct('giveup');
  });
  document.getElementById('yz-cancel').addEventListener('click', cancelYzRoom);
  document.getElementById('yz-back-lobby').addEventListener('click', backToYzLobby);
}

function renderYzRoom(state) {
  yzState = state;
  document.getElementById('yz-progress').textContent = `进度 ${state.progress}/12`;
  document.getElementById('yz-code-show').textContent = state.code;
  const waitCode = document.getElementById('yz-wait-code');
  if (waitCode) waitCode.textContent = state.code;

  const diceSig = state.dice.map((d) => d.value).join(',');
  if (diceSig !== yzDiceSig) { yzDiceSig = diceSig; yzSelected = new Set(); }

  const isWaiting = state.phase === 'waiting';
  const isPlay = state.phase === 'playing';
  const isOver = state.phase === 'finished';
  fkToggle('yz-waiting', isWaiting);
  fkToggle('yz-play', isPlay);
  fkToggle('yz-result', isOver);

  const spectator = !state.is_player;
  document.getElementById('yz-spectate-badge').classList.toggle('hidden', !spectator);
  document.getElementById('yz-giveup').classList.toggle('hidden', isWaiting || isOver || spectator);
  if (isWaiting) {
    document.getElementById('yz-count').textContent = state.players.length;
    document.getElementById('yz-start').classList.toggle('hidden', spectator || state.my_index !== 0);
    document.getElementById('yz-cancel').classList.toggle('hidden', spectator || state.my_index !== 0);
  }

  renderYzPlayers(state);
  if (isPlay) { renderYzDice(state); renderYzTable(state); }
  if (isOver) renderYzResult(state);
  renderYzLog(state);
}

function renderYzPlayers(state) {
  const wrap = document.getElementById('yz-players');
  wrap.innerHTML = '';
  state.players.forEach((p, i) => {
    const div = document.createElement('div');
    div.className = 'fk-player'
      + (i === state.turn && state.phase === 'playing' ? ' active' : '')
      + (i === state.my_index ? ' you' : '');
    div.innerHTML = `<div class="pname">${esc(p.name)}${i === state.my_index ? '（你）' : ''}`
      + `${p.given_up ? '（已放弃）' : ''}</div>`
      + `<div class="ptotal">${p.total} 分</div>`;
    wrap.appendChild(div);
  });
}

function renderYzDice(state) {
  const canSelect = state.is_turn && state.roll < YZ_MAX_ROLL;
  const wrap = document.getElementById('yz-dice');
  wrap.innerHTML = '';
  state.dice.forEach((d, i) => {
    const el = dieEl(d, { selectable: canSelect, selected: yzSelected.has(i) });
    if (canSelect) {
      el.addEventListener('click', () => {
        if (yzSelected.has(i)) yzSelected.delete(i);
        else yzSelected.add(i);
        renderYzRoom(yzState);
      });
    }
    wrap.appendChild(el);
  });
  const p = state.players[state.turn] || {};
  document.getElementById('yz-turn-label').textContent = state.is_turn
    ? '轮到你行动'
    : `${p.name} 正在行动……`;
  document.getElementById('yz-turn-label').classList.toggle('waiting', !state.is_turn);
  document.getElementById('yz-roll-label').textContent = `第 ${state.roll}/${YZ_MAX_ROLL} 投`;
  document.getElementById('yz-reroll').disabled = !(state.is_turn && state.roll < YZ_MAX_ROLL);
}

function renderYzTable(state) {
  const wrap = document.getElementById('yz-table');
  const cats = state.categories || [];
  let html = '<table class="yz-table"><thead><tr><th class="yz-rowlabel"></th>';
  state.players.forEach((p, i) => {
    html += `<th class="${i === state.turn ? 'active' : ''}${i === state.my_index ? ' you' : ''}">`
      + `${esc(p.name)}${i === state.my_index ? '（你）' : ''}</th>`;
  });
  html += '</tr></thead><tbody>';
  cats.forEach((name, r) => {
    html += `<tr><td class="yz-rowlabel">${esc(name)}</td>`;
    state.players.forEach((p, i) => {
      const v = p.score[r];
      const can = state.is_turn && i === state.my_index && v === null;
      html += `<td class="yz-cell${can ? ' clickable' : ''}${v === null ? ' empty' : ''}" data-r="${r}">`
        + (v === null ? (can ? '计分' : '·') : v) + '</td>';
    });
    html += '</tr>';
  });
  html += '<tr class="yz-bonus"><td class="yz-rowlabel">奖励分</td>';
  state.players.forEach((p) => { html += `<td>${p.bonus ? p.bonus : '·'}</td>`; });
  html += '</tr>';
  html += '<tr class="yz-total"><td class="yz-rowlabel">总分</td>';
  state.players.forEach((p) => { html += `<td>${p.total}</td>`; });
  html += '</tr></tbody></table>';
  wrap.innerHTML = html;
  wrap.querySelectorAll('.yz-cell.clickable').forEach((td) => {
    td.addEventListener('click', () => yzAct('score', { index: Number(td.dataset.r) }));
  });
}

function renderYzResult(state) {
  const lines = state.result_lines || [];
  const box = document.getElementById('yz-result');
  box.innerHTML =
    '<div class="panel-title">对局结束</div>'
    + lines.map((l) => `<div class="line">${esc(l)}</div>`).join('')
    + rematchButton('yz', state.is_player);
  bindRematch(box, 'yz', rematchYz);
}

function renderYzLog(state) {
  const box = document.getElementById('yz-log');
  box.innerHTML = '';
  state.log.forEach((l) => {
    const d = document.createElement('div');
    d.textContent = l;
    box.appendChild(d);
  });
  box.scrollTop = box.scrollHeight;
}

document.getElementById('btn-yahtzee').addEventListener('click', enterYahtzee);
document.getElementById('btn-yz-back').addEventListener('click', () => {
  closeGamePanels();
  refresh();
});
document.getElementById('btn-yz-create').addEventListener('click', createYzRoom);

// ==================== 17步麻将 网页版 ====================

const mjPanel = document.getElementById('mahjong-panel');
const mjLobby = document.getElementById('mj-lobby');
const mjRoom = document.getElementById('mj-room');
const mjRooms = document.getElementById('mj-rooms');
const mjLobbyMsg = document.getElementById('mj-lobby-msg');
const mjToast = document.getElementById('mj-toast');

const MJ_LAST_TURN = 17;

let mjCode = null;
let mjState = null;
let mjSig = null;
let mjMy34Sig = null;
let mjSel = new Set();
let mjLobbyTimer = null;
let mjRoomTimer = null;
let mjToastTimer = null;

function mjMsg(text, ok) {
  mjToast.textContent = text || '';
  mjToast.classList.toggle('ok', !!ok);
  clearTimeout(mjToastTimer);
  if (text) mjToastTimer = setTimeout(() => { mjToast.textContent = ''; }, 4000);
}

function mjTileLabel(i) {
  const suit = 'mpsz'[Math.floor(i / 10)];
  return (i % 10) + suit;
}

function tileImg(i) {
  return `<img class="tile" src="/mahjong/mj${i}.png" alt="${mjTileLabel(i)}" title="${mjTileLabel(i)}">`;
}

function tilesToText(tiles) {
  const groups = { m: [], p: [], s: [], z: [] };
  tiles.forEach((t) => { groups['mpsz'[Math.floor(t / 10)]].push(t % 10); });
  let out = '';
  ['m', 'p', 's', 'z'].forEach((s) => {
    if (groups[s].length) out += groups[s].sort((a, b) => a - b).join('') + s;
  });
  return out;
}

function mjChips(container, tiles, opts) {
  opts = opts || {};
  container.innerHTML = '';
  (tiles || []).forEach((t, i) => {
    const span = document.createElement('span');
    span.className = 'tile-chip' + (opts.selected && opts.selected.has(i) ? ' picked' : '');
    span.innerHTML = tileImg(t);
    if (opts.onClick) span.addEventListener('click', () => opts.onClick(i, t));
    container.appendChild(span);
  });
}

function mjDiscardRow(label, row, active) {
  let html = `<div class="mj-discard-row${active ? ' active' : ''}">`
    + `<span class="mj-disc-label">${esc(label)}</span><span class="mj-discard-pool">`;
  row.forEach((t) => { html += `<span class="tile-chip sm">${tileImg(t)}</span>`; });
  return html + '</span></div>';
}

async function enterMahjong() {
  loginPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
  pwdPanel.classList.add('hidden');
  mjPanel.classList.remove('hidden');
  mjLobby.classList.remove('hidden');
  mjRoom.classList.add('hidden');
  mjCode = null;
  mjLobbyMsg.textContent = '';
  const { status, data } = await api('/api/mahjong17/mine');
  if (status === 401) { mjPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 200 && data.ok && data.code) { enterMjRoom(data.code); return; }
  await refreshMjRooms();
  clearInterval(mjRoomTimer);
  mjRoomTimer = null;
  mjLobbyTimer = setInterval(refreshMjRooms, 2500);
}

function backToMjLobby() {
  clearInterval(mjRoomTimer);
  mjRoomTimer = null;
  mjCode = null;
  hideChat('mj');
  mjRoom.classList.add('hidden');
  mjLobby.classList.remove('hidden');
  refreshMjRooms();
  clearInterval(mjLobbyTimer);
  mjLobbyTimer = setInterval(refreshMjRooms, 2500);
}

async function refreshMjRooms() {
  const { status, data } = await api('/api/mahjong17/rooms');
  if (status === 401) { clearInterval(mjLobbyTimer); mjPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  mjRooms.innerHTML = '';
  if (!data.rooms.length) {
    const p = document.createElement('p');
    p.className = 'room-empty';
    p.textContent = '还没有房间，创建一个等对手来吧';
    mjRooms.appendChild(p);
    return;
  }
  data.rooms.forEach((r) => {
    const row = document.createElement('div');
    row.className = 'room-row';
    const ongoing = r.phase !== 'waiting';
    const meta = document.createElement('div');
    meta.className = 'room-meta';
    meta.textContent = (ongoing ? '对局中 · ' : '')
      + (r.stones ? '猫眼石局' : '普通局') + ` · 房间号 ${r.code}`;
    const host = document.createElement('div');
    host.className = 'room-host';
    host.textContent = ongoing ? (r.players || []).join(' vs ') : r.host;
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary btn-sm';
    btn.textContent = ongoing ? '观战' : '加入';
    btn.addEventListener('click', () => (ongoing ? enterMjRoom(r.code) : joinMjRoom(r.code)));
    row.appendChild(host);
    row.appendChild(meta);
    row.appendChild(btn);
    mjRooms.appendChild(row);
  });
}

async function createMjRoom() {
  mjLobbyMsg.textContent = '';
  const stones = document.getElementById('mj-stones-on').checked;
  const { status, data } = await api('/api/mahjong17/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stones: stones }),
  });
  if (status === 200 && data.ok) enterMjRoom(data.code);
  else mjLobbyMsg.textContent = data.msg || '创建失败喵';
}

async function joinMjRoom(code) {
  mjLobbyMsg.textContent = '';
  const { status, data } = await api('/api/mahjong17/join', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  });
  if (status === 200 && data.ok) enterMjRoom(data.code);
  else mjLobbyMsg.textContent = data.msg || '加入失败喵';
}

async function cancelMjRoom() {
  if (!mjCode) return;
  const { status, data } = await api('/api/mahjong17/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: mjCode }),
  });
  if (status === 200 && data.ok) backToMjLobby();
  else mjMsg(data.msg || '取消失败喵');
}

async function mjAct(action, extra) {
  if (!mjCode) return false;
  const body = Object.assign({ code: mjCode, action: action }, extra || {});
  const { status, data } = await api('/api/mahjong17/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (status === 200 && data.ok) {
    mjSig = mjSignature(data.room);
    renderMjRoom(data.room);
    return true;
  }
  if (data && data.need_confirm) {
    if (window.confirm(data.msg || '这套牌暂时听不了牌喵，确定要这样选吗？')) {
      return mjAct(action, Object.assign({}, extra || {}, { confirm: true }));
    }
    return false;
  }
  mjMsg(data.msg || '操作失败喵');
  return false;
}

function mjSignature(r) {
  return JSON.stringify([
    r.phase, r.turn, r.player_turn, r.dora, r.discards,
    r.hand, r.left, r.my34, r.furiten, r.result, r.log.length,
  ]);
}

async function enterMjRoom(code) {
  clearInterval(mjLobbyTimer);
  mjLobbyTimer = null;
  mjCode = code;
  mjState = null;
  mjSig = null;
  mjMy34Sig = null;
  mjSel = new Set();
  mjLobby.classList.add('hidden');
  mjRoom.classList.remove('hidden');
  showChat('mj');
  buildMjRoomDom();
  await pollMjRoom();
  clearInterval(mjRoomTimer);
  mjRoomTimer = setInterval(pollMjRoom, 1200);
}

async function pollMjRoom() {
  const code = mjCode;
  if (!code) return;
  const { status, data } = await api('/api/mahjong17/state?code=' + encodeURIComponent(code));
  if (code !== mjCode) return;   // 已离开或换了房间，丢弃旧响应
  if (status === 401) { clearInterval(mjRoomTimer); mjPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 404) { mjMsg('房间已结束喵'); backToMjLobby(); return; }
  if (status !== 200 || !data.ok) return;
  const s = mjSignature(data.room);
  if (s !== mjSig) {
    mjSig = s;
    renderMjRoom(data.room);
  }
  renderChat('mj', data.room.chat);
}

function buildMjRoomDom() {
  mjRoom.innerHTML = `
    <div class="card fk-head">
      <div class="fk-head-top">
        <div class="fk-title">17步麻将<span id="mj-stones-show"></span></div>
        <div class="fk-head-right">
          <div class="fk-code">房间号 <b id="mj-code-show"></b></div>
          <div id="mj-spectate-badge" class="fk-spectate hidden">观战中</div>
          <div id="mj-furiten" class="fk-furiten hidden">振听中：本局不能再荣和</div>
        </div>
      </div>
      <div id="mj-players" class="fk-players"></div>
    </div>

    <div id="mj-waiting" class="card fk-card hidden">
      <div class="fk-info">等待另一位玩家加入……把房间号 <b id="mj-wait-code"></b> 发给对手即可</div>
      <div class="actions"><button id="mj-cancel" class="btn btn-ghost btn-sm">解散房间</button></div>
    </div>

    <div id="mj-select" class="card fk-card hidden">
      <div class="panel-title">选择 13 张手牌</div>
      <div class="mj-hint">宝牌指示牌：<span id="mj-dora-select"></span></div>
      <div id="mj-my34" class="tile-pool"></div>
      <div class="actions">
        <button id="mj-submit" class="btn btn-primary btn-sm">确认手牌</button>
        <span id="mj-count" class="hint"></span>
      </div>
    </div>

    <div id="mj-play" class="card fk-card hidden">
      <div class="mj-hint">宝牌指示牌：<span id="mj-dora-play"></span></div>
      <div class="mj-section">
        <div class="mj-label">牌桌 · 双方舍牌</div>
        <div id="mj-discards" class="mj-discards"></div>
      </div>
      <div class="mj-section">
        <div class="mj-label">我的手牌（13 张）</div>
        <div id="mj-myhand" class="tile-pool"></div>
      </div>
      <div class="mj-section">
        <div class="mj-label">舍牌候补（点选打出）</div>
        <div id="mj-myleft" class="tile-pool"></div>
      </div>
      <div class="actions">
        <button id="mj-ron" class="btn btn-primary btn-sm">荣和</button>
        <button id="mj-draw" class="btn btn-ghost btn-sm hidden">流局</button>
        <span id="mj-turn-hint" class="hint"></span>
      </div>
    </div>

    <div id="mj-spectate" class="card fk-card hidden">
      <div class="panel-title">观战视角</div>
      <div class="mj-hint">观战中：可以看到双方手牌与待排（舍牌候补）</div>
      <div class="mj-hint">宝牌指示牌：<span id="mj-dora-spec"></span></div>
      <div class="mj-section">
        <div class="mj-label">牌桌 · 双方舍牌</div>
        <div id="mj-discards-spec" class="mj-discards"></div>
      </div>
      <div id="mj-spectate-body"></div>
    </div>

    <div id="mj-result" class="card fk-result hidden"></div>

    <div class="card fk-card">
      <div class="panel-title">对局记录</div>
      <div id="mj-log" class="log"></div>
    </div>

    <div class="actions">
      <button id="mj-back-lobby" class="btn btn-ghost btn-sm">返回大厅</button>
    </div>`;

  document.getElementById('mj-submit').addEventListener('click', () => {
    const tiles = (mjState.my34 || []).filter((_, i) => mjSel.has(i));
    if (tiles.length !== 13) { mjMsg('需要正好选 13 张喵'); return; }
    mjAct('select', { text: tilesToText(tiles) });
  });
  document.getElementById('mj-ron').addEventListener('click', () => mjAct('play', { text: '荣' }));
  document.getElementById('mj-draw').addEventListener('click', () => mjAct('play', { text: '流局' }));
  document.getElementById('mj-cancel').addEventListener('click', cancelMjRoom);
  document.getElementById('mj-back-lobby').addEventListener('click', backToMjLobby);
}

function renderMjRoom(state) {
  mjState = state;
  document.getElementById('mj-code-show').textContent = state.code;
  document.getElementById('mj-stones-show').textContent = state.stones ? ' · 猫眼石局' : '';
  const waitCode = document.getElementById('mj-wait-code');
  if (waitCode) waitCode.textContent = state.code;

  const isWaiting = state.phase === 'waiting';
  const isSelect = state.phase === 'selecting';
  const isPlay = state.phase === 'playing';
  const isOver = state.phase === 'finished';
  const spectator = !state.is_player;
  fkToggle('mj-waiting', isWaiting);
  fkToggle('mj-select', isSelect && !spectator);
  fkToggle('mj-play', isPlay && !spectator);
  fkToggle('mj-spectate', spectator && (isSelect || isPlay));
  fkToggle('mj-result', isOver);

  document.getElementById('mj-spectate-badge').classList.toggle('hidden', !spectator);
  document.getElementById('mj-furiten').classList.toggle('hidden', !(state.is_player && state.furiten));
  if (isWaiting) {
    document.getElementById('mj-cancel').classList.toggle('hidden', spectator || state.my_index !== 0);
  }

  const names = state.names || [];
  const wrap = document.getElementById('mj-players');
  wrap.innerHTML = '';
  names.forEach((n, i) => {
    const div = document.createElement('div');
    div.className = 'fk-player'
      + (i === state.player_turn && isPlay ? ' active' : '')
      + (i === state.my_index ? ' you' : '');
    div.innerHTML = `<div class="pname">${esc(n || '等待中')}${i === state.my_index ? '（你）' : ''}</div>`
      + `<div class="pmeta">${i === state.player_turn && isPlay ? '行动中' : ''}</div>`;
    wrap.appendChild(div);
  });

  if (isSelect && !spectator) renderMjSelect(state);
  if (isPlay && !spectator) renderMjPlay(state);
  if (spectator && (isSelect || isPlay)) renderMjSpectate(state);
  if (isOver) renderMjResult(state);
  renderMjLog(state);
}

function renderMjSpectate(state) {
  document.getElementById('mj-dora-spec').innerHTML = (state.dora || []).map(tileImg).join('');

  const disc = document.getElementById('mj-discards-spec');
  disc.innerHTML = '';
  (state.discards || []).forEach((row, i) => {
    const label = (state.names[i] || `P${i + 1}`);
    disc.insertAdjacentHTML('beforeend', mjDiscardRow(label, row, i === state.player_turn));
  });

  const showPool = state.phase === 'selecting';
  const html = [];
  (state.spectate || []).forEach((r) => {
    html.push(`<div class="mj-reveal"><div class="mj-label">${esc(r.name || '等待中')}</div>`);
    if (showPool) {
      html.push(`<div class="mj-label">发牌（${(r.pool || []).length} 张）</div>`
        + `<div class="tile-pool">${(r.pool || []).map((t) => tileImg(t)).join('')}</div>`);
    }
    html.push(`<div class="mj-label">手牌（${(r.hand || []).length} 张）</div>`
      + `<div class="tile-pool">${(r.hand || []).map((t) => tileImg(t)).join('')}</div>`);
    if (!showPool) {
      html.push(`<div class="mj-label">待排（${(r.left || []).length} 张）</div>`
        + `<div class="tile-pool">${(r.left || []).map((t) => tileImg(t)).join('')}</div>`);
    }
    html.push('</div>');
  });
  document.getElementById('mj-spectate-body').innerHTML = html.join('');
}

function renderMjSelect(state) {
  const dora = (state.dora || []).map(tileImg).join('');
  document.getElementById('mj-dora-select').innerHTML = dora;
  const done = (state.hand || []).length === 13;
  const my34 = state.my34 || [];
  const pool = document.getElementById('mj-my34');
  mjChips(pool, my34, {
    selected: mjSel,
    onClick: done ? null : (i) => {
      if (mjSel.has(i)) mjSel.delete(i);
      else if (mjSel.size < 13) mjSel.add(i);
      else { mjMsg('最多选 13 张喵'); return; }
      renderMjRoom(mjState);
    },
  });
  pool.classList.toggle('disabled', done);
  const btn = document.getElementById('mj-submit');
  const cnt = document.getElementById('mj-count');
  if (done) {
    cnt.textContent = '已确认手牌，等待对手选牌……';
    btn.classList.add('hidden');
  } else {
    cnt.textContent = `已选 ${mjSel.size}/13`;
    btn.classList.remove('hidden');
    btn.disabled = mjSel.size !== 13;
  }
}

function renderMjPlay(state) {
  document.getElementById('mj-dora-play').innerHTML = (state.dora || []).map(tileImg).join('');

  const disc = document.getElementById('mj-discards');
  disc.innerHTML = '';
  (state.discards || []).forEach((row, i) => {
    const label = (state.names[i] || `P${i + 1}`) + (i === state.my_index ? '（你）' : '');
    disc.insertAdjacentHTML('beforeend', mjDiscardRow(label, row, i === state.player_turn));
  });

  mjChips(document.getElementById('mj-myhand'), state.hand || []);

  const myTurn = state.is_turn;
  const atLast = state.turn >= MJ_LAST_TURN;
  mjChips(document.getElementById('mj-myleft'), state.left || [], {
    onClick: (i, t) => {
      if (!myTurn) { mjMsg('当前不是你的回合喵'); return; }
      if (atLast) { mjMsg('最后一巡只能荣和或流局喵'); return; }
      mjAct('play', { text: mjTileLabel(t) });
    },
  });

  const hint = document.getElementById('mj-turn-hint');
  hint.textContent = myTurn
    ? (atLast ? '最后一巡：只能「荣和」或「流局」' : '轮到你：点「舍牌候补」里的牌打出，或点「荣和」')
    : '等待对手行动……';
  document.getElementById('mj-ron').disabled = !myTurn;
  document.getElementById('mj-draw').classList.toggle('hidden', !(myTurn && atLast));
}

function renderMjResult(state) {
  const res = state.result || {};
  const lines = [];
  if (res.winner === null || res.winner === undefined) {
    lines.push('本局无胜负');
  } else {
    lines.push(`🏆 ${esc((state.names || [])[res.winner] || '')} 获胜`);
  }
  lines.push(`结果：${esc(res.reason || '')}`);
  if (res.fan === 0 && res.pid !== null && res.pid !== undefined && res.cut !== null) {
    lines.push('（宣布荣和但无役，按诈胡处理）');
  }
  if (res.score) {
    if (res.fan >= 100) lines.push(`得分 ${res.score} 点`);
    else if (res.fan > 0) lines.push(`${res.fu}符 ${res.fan}番 · ${res.score} 点`);
  }
  (res.fans || []).forEach((f) => {
    const name = Array.isArray(f) ? f[0] : f;
    const val = Array.isArray(f) ? f[1] : '';
    lines.push(`· ${esc(name)}${val ? ' ' + esc(val) : ''}`);
  });
  (res.lines || []).forEach((l) => lines.push(l));

  const html = ['<div class="panel-title">对局结束</div>']
    .concat(lines.map((l) => `<div class="line">${esc(l)}</div>`));
  if (state.reveal) {
    state.reveal.forEach((r) => {
      html.push('<div class="mj-reveal">'
        + `<div class="mj-label">${esc(r.name)} 手牌（${r.hand.length} 张）</div>`
        + `<div class="tile-pool">${r.hand.map((t) => tileImg(t)).join('')}</div>`
        + `<div class="mj-label">舍牌（${r.discards.length} 张）</div>`
        + `<div class="tile-pool">${r.discards.map((t) => tileImg(t)).join('')}</div>`
        + `<div class="mj-label">剩余未打出（${(r.left || []).length} 张）</div>`
        + `<div class="tile-pool">${(r.left || []).map((t) => tileImg(t)).join('')}</div>`
        + '</div>');
    });
  }
  document.getElementById('mj-result').innerHTML = html.join('') + rematchButton('mj', state.is_player);
  bindRematch(document.getElementById('mj-result'), 'mj', rematchMj);
}

function renderMjLog(state) {
  const box = document.getElementById('mj-log');
  box.innerHTML = '';
  (state.log || []).forEach((l) => {
    const d = document.createElement('div');
    d.textContent = l;
    box.appendChild(d);
  });
  box.scrollTop = box.scrollHeight;
}

document.getElementById('btn-mahjong').addEventListener('click', enterMahjong);
document.getElementById('btn-mj-back').addEventListener('click', () => {
  closeGamePanels();
  refresh();
});
document.getElementById('btn-mj-create').addEventListener('click', createMjRoom);

// ==================== 麻酱宝藏（印加宝藏麻将版） ====================

const goldPanel = document.getElementById('gold-panel');
const goldLobby = document.getElementById('gold-lobby');
const goldRoom = document.getElementById('gold-room');
const goldRooms = document.getElementById('gold-rooms');
const goldLobbyMsg = document.getElementById('gold-lobby-msg');
const goldToast = document.getElementById('gold-toast');

const GOLD_MISTAKE_NAMES = ['舞蹈', '诈立', '错吃', '诈和', '夏哒！'];

let goldCode = null;
let goldState = null;
let goldSig = null;
let goldLobbyTimer = null;
let goldRoomTimer = null;
let goldToastTimer = null;

function goldMsg(text, ok) {
  goldToast.textContent = text || '';
  goldToast.classList.toggle('ok', !!ok);
  clearTimeout(goldToastTimer);
  if (text) goldToastTimer = setTimeout(() => { goldToast.textContent = ''; }, 4000);
}

function goldCardImg(card) {
  return `<img class="mg-card" src="/mgold/${card.id}.png" alt="${esc(card.label)}"`
    + ` title="${esc(card.label)}">`;
}

async function enterGold() {
  loginPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
  pwdPanel.classList.add('hidden');
  goldPanel.classList.remove('hidden');
  goldLobby.classList.remove('hidden');
  goldRoom.classList.add('hidden');
  goldCode = null;
  goldLobbyMsg.textContent = '';
  const { status, data } = await api('/api/mahjong_gold/mine');
  if (status === 401) { goldPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 200 && data.ok && data.code) { enterGoldRoom(data.code); return; }
  await refreshGoldRooms();
  clearInterval(goldRoomTimer);
  goldRoomTimer = null;
  clearInterval(goldLobbyTimer);
  goldLobbyTimer = setInterval(refreshGoldRooms, 2500);
}

function backToGoldLobby() {
  clearInterval(goldRoomTimer);
  goldRoomTimer = null;
  goldCode = null;
  hideChat('gold');
  goldRoom.classList.add('hidden');
  goldLobby.classList.remove('hidden');
  refreshGoldRooms();
  clearInterval(goldLobbyTimer);
  goldLobbyTimer = setInterval(refreshGoldRooms, 2500);
}

async function refreshGoldRooms() {
  const { status, data } = await api('/api/mahjong_gold/rooms');
  if (status === 401) { clearInterval(goldLobbyTimer); goldPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  goldRooms.innerHTML = '';
  if (!data.rooms.length) {
    const p = document.createElement('p');
    p.className = 'room-empty';
    p.textContent = '还没有房间，创建一个等队友来吧';
    goldRooms.appendChild(p);
    return;
  }
  data.rooms.forEach((r) => {
    const row = document.createElement('div');
    row.className = 'room-row';
    const ongoing = r.phase !== 'waiting';
    const meta = document.createElement('div');
    meta.className = 'room-meta';
    meta.textContent = (ongoing ? '探险中 · ' : '等待中 · ')
      + `房间号 ${r.code} · ${r.count}/${r.max} 人`;
    const host = document.createElement('div');
    host.className = 'room-host';
    host.textContent = ongoing ? (r.players || []).join(' / ') : r.host;
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary btn-sm';
    btn.textContent = ongoing ? '观战' : '加入';
    btn.addEventListener('click', () => (ongoing ? enterGoldRoom(r.code) : joinGoldRoom(r.code)));
    row.appendChild(host);
    row.appendChild(meta);
    row.appendChild(btn);
    goldRooms.appendChild(row);
  });
}

async function createGoldRoom() {
  goldLobbyMsg.textContent = '';
  const { status, data } = await api('/api/mahjong_gold/create', { method: 'POST' });
  if (status === 200 && data.ok) enterGoldRoom(data.code);
  else goldLobbyMsg.textContent = data.msg || '创建失败喵';
}

async function joinGoldRoom(code) {
  goldLobbyMsg.textContent = '';
  const { status, data } = await api('/api/mahjong_gold/join', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  });
  if (status === 200 && data.ok) enterGoldRoom(data.code);
  else goldLobbyMsg.textContent = data.msg || '加入失败喵';
}

async function cancelGoldRoom() {
  if (!goldCode) return;
  const { status, data } = await api('/api/mahjong_gold/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: goldCode }),
  });
  if (status === 200 && data.ok) backToGoldLobby();
  else goldMsg(data.msg || '取消失败喵');
}

async function goldAct(action) {
  if (!goldCode) return;
  const { status, data } = await api('/api/mahjong_gold/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: goldCode, action: action }),
  });
  if (status === 200 && data.ok) {
    goldSig = goldSignature(data.room);
    renderGoldRoom(data.room);
    renderChat('gold', data.room.chat);
  } else {
    goldMsg(data.msg || '操作失败喵');
  }
}

function goldSignature(r) {
  return JSON.stringify([
    r.phase, r.round, r.pot_gold, r.pot_yakuman, r.turn_score, r.deck_left,
    (r.revealed || []).map((c) => c.id), r.mistake_left, r.can_decide,
    r.players, r.result, r.log.length,
  ]);
}

async function enterGoldRoom(code) {
  clearInterval(goldLobbyTimer);
  goldLobbyTimer = null;
  goldCode = code;
  goldState = null;
  goldSig = null;
  goldLobby.classList.add('hidden');
  goldRoom.classList.remove('hidden');
  showChat('gold');
  buildGoldRoomDom();
  await pollGoldRoom();
  clearInterval(goldRoomTimer);
  goldRoomTimer = setInterval(pollGoldRoom, 1200);
}

async function pollGoldRoom() {
  const code = goldCode;
  if (!code) return;
  const { status, data } = await api('/api/mahjong_gold/state?code=' + encodeURIComponent(code));
  if (code !== goldCode) return;   // 已离开或换了房间，丢弃旧响应
  if (status === 401) { clearInterval(goldRoomTimer); goldPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 404) { goldMsg('房间已结束喵'); backToGoldLobby(); return; }
  if (status !== 200 || !data.ok) return;
  const s = goldSignature(data.room);
  if (s !== goldSig) {
    goldSig = s;
    renderGoldRoom(data.room);
  }
  renderChat('gold', data.room.chat);
}

function buildGoldRoomDom() {
  goldRoom.innerHTML = `
    <div class="card fk-head">
      <div class="fk-head-top">
        <div class="fk-title">麻酱宝藏<span id="gold-round-show"></span></div>
        <div class="fk-head-right">
          <div class="fk-code">房间号 <b id="gold-code-show"></b></div>
          <div id="gold-spectate-badge" class="fk-spectate hidden">观战中</div>
        </div>
      </div>
      <div id="gold-players" class="fk-players mg-players"></div>
    </div>

    <div id="gold-waiting" class="card fk-card hidden">
      <div class="fk-info">等待玩家加入……把房间号 <b id="gold-wait-code"></b> 发给大家，2~5 人，满 5 人自动开始</div>
      <div class="actions">
        <button id="gold-start" class="btn btn-primary btn-sm">开始探险</button>
        <button id="gold-add-bot" class="btn btn-ghost btn-sm">添加机器人</button>
        <button id="gold-cancel" class="btn btn-ghost btn-sm">解散房间</button>
      </div>
      <p id="gold-wait-hint" class="hint"></p>
    </div>

    <div id="gold-explore" class="card fk-card hidden">
      <div class="mg-pools">
        <div class="mg-pool"><div class="mg-pool-num" id="gold-turn-score">0</div><div class="mg-pool-label">本轮携带</div></div>
        <div class="mg-pool"><div class="mg-pool-num" id="gold-pot-gold">0</div><div class="mg-pool-label">点棒池</div></div>
        <div class="mg-pool"><div class="mg-pool-num" id="gold-pot-yakuman">0</div><div class="mg-pool-label">役满池</div></div>
        <div class="mg-pool"><div class="mg-pool-num" id="gold-deck-left">0</div><div class="mg-pool-label">牌堆剩余</div></div>
      </div>
      <div class="mj-section">
        <div class="mj-label">本轮已翻开</div>
        <div id="gold-revealed" class="mg-card-row"></div>
      </div>
      <div id="gold-yakuman-tip" class="mg-yakuman-tip"></div>
      <div class="mj-section">
        <div class="mj-label">陷阱剩余张数</div>
        <div id="gold-mistakes" class="mg-mistakes"></div>
      </div>
      <div class="actions">
        <button id="gold-continue" class="btn btn-primary btn-sm">继续</button>
        <button id="gold-leave" class="btn btn-ghost btn-sm">下车</button>
        <span id="gold-decide-hint" class="hint"></span>
      </div>
    </div>

    <div id="gold-result" class="card fk-result hidden"></div>

    <div class="card fk-card">
      <div class="panel-title">探险记录</div>
      <div id="gold-log" class="log"></div>
    </div>

    <div class="actions">
      <button id="gold-back-lobby" class="btn btn-ghost btn-sm">返回大厅</button>
    </div>`;

  document.getElementById('gold-start').addEventListener('click', () => goldAct('start'));
  document.getElementById('gold-add-bot').addEventListener('click', () => goldAct('add_bot'));
  document.getElementById('gold-continue').addEventListener('click', () => goldAct('continue'));
  document.getElementById('gold-leave').addEventListener('click', () => goldAct('leave'));
  document.getElementById('gold-cancel').addEventListener('click', cancelGoldRoom);
  document.getElementById('gold-back-lobby').addEventListener('click', backToGoldLobby);
}

function renderGoldRoom(state) {
  goldState = state;
  document.getElementById('gold-code-show').textContent = state.code;
  document.getElementById('gold-round-show').textContent =
    state.phase === 'waiting' ? '' : ` · 第 ${state.round}/${state.rounds} 轮`;
  const waitCode = document.getElementById('gold-wait-code');
  if (waitCode) waitCode.textContent = state.code;

  const isWaiting = state.phase === 'waiting';
  const isExploring = state.phase === 'exploring';
  const isOver = state.phase === 'finished';
  const spectator = !state.is_player;

  fkToggle('gold-waiting', isWaiting);
  fkToggle('gold-explore', isExploring);
  fkToggle('gold-result', isOver);
  document.getElementById('gold-spectate-badge').classList.toggle('hidden', !spectator);

  if (isWaiting) {
    const host = state.my_index === 0;
    document.getElementById('gold-start').classList.toggle('hidden', !host);
    document.getElementById('gold-cancel').classList.toggle('hidden', !host);
    const addBot = document.getElementById('gold-add-bot');
    addBot.classList.toggle('hidden', !host);
    addBot.disabled = (state.players || []).length >= 5;
    document.getElementById('gold-wait-hint').textContent =
      host ? '房主可以添加机器人，或开始探险（至少 2 人）' : '等房主开始探险';
  }

  const wrap = document.getElementById('gold-players');
  wrap.innerHTML = '';
  (state.players || []).forEach((p, i) => {
    const div = document.createElement('div');
    const active = isExploring && !p.left;
    div.className = 'fk-player' + (active ? ' active' : '') + (i === state.my_index ? ' you' : '');
    let meta;
    if (isWaiting) meta = '等待中';
    else if (p.left) meta = '本轮已下车';
    else if (!p.decided) meta = '待决定';
    else meta = '已决定';
    div.innerHTML = `<div class="pname">${esc(p.name || '等待中')}${i === state.my_index ? '（你）' : ''}`
      + `${p.bot ? ' · 机器人' : ''}</div>`
      + `<div class="pmeta">${meta}</div>`
      + `<div class="ptotal">${p.score} 根</div>`;
    wrap.appendChild(div);
  });

  if (isExploring) renderGoldExplore(state);
  if (isOver) renderGoldResult(state);
  renderGoldLog(state);
}

function renderGoldExplore(state) {
  document.getElementById('gold-turn-score').textContent = state.turn_score;
  document.getElementById('gold-pot-gold').textContent = state.pot_gold;
  document.getElementById('gold-pot-yakuman').textContent = state.pot_yakuman;
  document.getElementById('gold-deck-left').textContent = state.deck_left;

  const revealed = document.getElementById('gold-revealed');
  revealed.innerHTML = '';
  if (!(state.revealed || []).length) {
    revealed.innerHTML = '<span class="hint">还没有翻牌喵</span>';
  } else {
    state.revealed.forEach((c) => {
      const extra = c.type === 'yakuman' ? ` +${c.value}`
        : c.type === 'mistake' ? ' 陷阱' : '';
      revealed.insertAdjacentHTML('beforeend',
        `<figure class="mg-card-item ${c.type}">${goldCardImg(c)}`
        + `<figcaption>${esc(c.label)}${extra}</figcaption></figure>`);
    });
  }

  const tip = document.getElementById('gold-yakuman-tip');
  tip.textContent = state.yakuman_card
    ? `本轮新增役满牌：${state.yakuman_card.label}（${state.yakuman_card.value} 根）`
    : '';

  const mistakes = document.getElementById('gold-mistakes');
  mistakes.innerHTML = '';
  (state.mistake_left || []).forEach((n, i) => {
    mistakes.insertAdjacentHTML('beforeend',
      `<span class="mg-mistake${n ? '' : ' gone'}">${esc(GOLD_MISTAKE_NAMES[i])} × ${n}</span>`);
  });

  const canDecide = !!state.can_decide;
  document.getElementById('gold-continue').disabled = !canDecide;
  document.getElementById('gold-leave').disabled = !canDecide;
  let hint;
  if (!state.is_player) hint = '观战中';
  else if (state.can_decide) hint = '继续翻牌，还是带着点棒下车？';
  else if (state.players[state.my_index].left) hint = '你本轮已经下车，等其他人结束';
  else hint = '等本轮其他人做决定……';
  document.getElementById('gold-decide-hint').textContent = hint;
}

function renderGoldResult(state) {
  const box = document.getElementById('gold-result');
  const ranking = (state.result && state.result.ranking) || [];
  let html = '<div class="panel-title">五轮结束 · 最终排名</div>';
  ranking.forEach((r, i) => {
    html += `<div class="line">${i + 1}. ${esc(r.name || '玩家')}：${r.score} 根</div>`;
  });
  html += rematchButton('gold', state.is_player);
  box.innerHTML = html;
  bindRematch(box, 'gold', rematchGold);
}

function renderGoldLog(state) {
  const box = document.getElementById('gold-log');
  box.innerHTML = '';
  (state.log || []).forEach((l) => {
    const d = document.createElement('div');
    d.textContent = l;
    box.appendChild(d);
  });
  box.scrollTop = box.scrollHeight;
}

document.getElementById('btn-gold').addEventListener('click', enterGold);
document.getElementById('btn-gold-back').addEventListener('click', () => {
  closeGamePanels();
  refresh();
});
document.getElementById('btn-gold-create').addEventListener('click', createGoldRoom);

// ==================== UCML / UEML 赛事计分 ====================

const ucmlState = { data: null, rankView: '', matchView: 'all', formSig: '' };

function ucmlEsc(text) {
  return String(text == null ? '' : text).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[m]));
}

function ucmlColor(item) {
  return `rgb(${item.r == null ? 120 : item.r},${item.g == null ? 120 : item.g},${item.b == null ? 120 : item.b})`;
}

function ucmlTint(item) {
  return `rgba(${item.r == null ? 120 : item.r},${item.g == null ? 120 : item.g},${item.b == null ? 120 : item.b},0.16)`;
}

function ucmlTeamChip(name, item) {
  return `<span class="ucml-chip"><i style="background:${ucmlColor(item)}"></i>${ucmlEsc(name)}</span>`;
}

function ucmlSetMsg(text, ok) {
  const el = document.getElementById('ucml-msg');
  el.textContent = text || '';
  el.classList.toggle('ok', !!ok);
}

function ucmlRankOptions() {
  const d = ucmlState.data;
  if (!d) return ['total'];
  const opts = ['total'];
  if (d.stage >= 1 || d.stage === 4) opts.push('1');
  if (d.stage >= 2 || d.stage === 4) opts.push('2');
  if (d.stage >= 3 || d.stage === 4) opts.push('3');
  return opts;
}

const UCML_RANK_LABELS = { total: '总成绩', 1: '常规赛', 2: '半决赛', 3: '决赛' };

async function loadUcml(season) {
  const query = season == null ? '' : `?season=${encodeURIComponent(season)}`;
  const { status, data } = await api(`/api/ucml/overview${query}`);
  if (status === 404 && season != null) {
    return loadUcml();
  }
  if (status !== 200 || !data.ok) {
    ucmlSetMsg((data && data.msg) || '读取计分数据失败喵', false);
    return;
  }
  ucmlState.data = data.data;
  const options = ucmlRankOptions();
  if (!options.includes(ucmlState.rankView)) {
    ucmlState.rankView = data.data.stage >= 1 ? String(Math.min(data.data.stage, 3)) : 'total';
  }
  renderUcml();
}

function ucmlApply(data, resetRank) {
  ucmlState.data = data;
  if (resetRank) {
    ucmlState.rankView = data.stage >= 1 ? String(Math.min(data.stage, 3)) : 'total';
  }
  const options = ucmlRankOptions();
  if (!options.includes(ucmlState.rankView)) ucmlState.rankView = 'total';
  renderUcml();
}

async function ucmlPost(path, body, onOk) {
  const { status, data } = await api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (status !== 200 || !data.ok) {
    ucmlSetMsg((data && data.msg) || '操作失败喵', false);
    return;
  }
  ucmlSetMsg('', false);
  if (onOk) onOk(data);
}

function renderUcml() {
  const d = ucmlState.data;
  if (!d) return;
  document.getElementById('ucml-sub').textContent = d.archived
    ? `第 ${d.season} 赛季 · 历史归档 · ${d.teams.length} 支队伍 / ${d.players.length} 位选手 · 共 ${d.matches.length} 场`
    : `第 ${d.season} 赛季 · ${d.stage_name} · ${d.teams.length} 支队伍 / ${d.players.length} 位选手 · 已记录 ${d.matches.length} 场`;
  renderUcmlSeasonBar(d);
  renderUcmlAdminActions(d);
  renderUcmlScore(d);
  renderUcmlStandings(d);
  renderUcmlMatches(d);
  renderUcmlRoster(d);
}

function renderUcmlSeasonBar(d) {
  const bar = document.getElementById('ucml-season-bar');
  const archived = (d.seasons || []).slice().sort((a, b) => b - a);
  const items = [
    `<button class="seg-btn${d.archived ? '' : ' is-active'}" data-ucml-season="" type="button">第 ${d.current_season} 赛季</button>`,
  ];
  archived.forEach((n) => {
    items.push(`<button class="seg-btn${d.archived && d.season === n ? ' is-active' : ''}" data-ucml-season="${n}" type="button">第 ${n} 赛季 · 历史</button>`);
  });
  bar.innerHTML = items.join('');
  bar.querySelectorAll('[data-ucml-season]').forEach((btn) => {
    btn.addEventListener('click', () => {
      ucmlSetMsg('', false);
      loadUcml(btn.dataset.ucmlSeason ? Number(btn.dataset.ucmlSeason) : null);
    });
  });
}

function renderUcmlAdminActions(d) {
  const box = document.getElementById('ucml-admin-actions');
  if (d.archived) {
    box.innerHTML = '<span class="hint">历史赛季 · 只读</span>';
    return;
  }
  if (!d.is_admin) {
    box.innerHTML = '<span class="hint">计分与赛事管理仅限两位管理员</span>';
    return;
  }
  const buttons = [];
  if (d.stage < 4) {
    const labels = { 0: '开始常规赛', 1: '进入半决赛', 2: '进入决赛', 3: '结束赛季' };
    buttons.push(`<button class="btn btn-primary btn-sm" data-ucml="next" type="button">${labels[d.stage] || '下一阶段'}</button>`);
  } else {
    buttons.push('<button class="btn btn-primary btn-sm" data-ucml="newseason" type="button">开始新赛季</button>');
  }
  if (d.can_undo) {
    buttons.push('<button class="btn btn-ghost btn-sm" data-ucml="undo" type="button">撤回最近一场</button>');
  }
  box.innerHTML = buttons.join('');
  box.querySelectorAll('[data-ucml]').forEach((btn) => {
    btn.addEventListener('click', () => ucmlAdminAction(btn.dataset.ucml));
  });
}

async function ucmlAdminAction(kind) {
  const paths = { next: '/api/ucml/stage/next', undo: '/api/ucml/match/undo', newseason: '/api/ucml/season/new' };
  const names = { next: '推进阶段', undo: '撤回最近一场比赛', newseason: '开始新赛季' };
  const confirmText = {
    next: '推进阶段',
    undo: '撤回最近一场比赛',
    newseason: '开始新赛季（当前赛季会归档保存，之后仍可随时查看）',
  };
  if (!confirm(`确定要${confirmText[kind]}吗喵？`)) return;
  await ucmlPost(paths[kind], {}, (data) => {
    ucmlSetMsg(`${names[kind]}成功喵`, true);
    ucmlState.formSig = '';
    ucmlApply(data.data, kind !== 'undo');
  });
}

// ---------- 单场计分表单 ----------

function ucmlFormSignature(d) {
  const table = d.stage_tables[String(d.stage)] || { teams: [] };
  const teams = (table.teams || []).map((t) => t.name).join('|');
  const players = d.players.map((p) => `${p.name}@${p.team}`).join('|');
  return `${d.stage}#${teams}#${players}`;
}

function renderUcmlScore(d) {
  const card = document.getElementById('ucml-score-card');
  const show = d.is_admin && !d.archived && d.stage >= 1 && d.stage <= 3;
  card.classList.toggle('hidden', !show);
  if (!show) return;
  const sig = ucmlFormSignature(d);
  if (sig !== ucmlState.formSig) {
    ucmlState.formSig = sig;
    buildUcmlForm(d);
  }
  ucmlUpdateSum();
}

function buildUcmlForm(d) {
  const wrap = document.getElementById('ucml-rows');
  const table = d.stage_tables[String(d.stage)] || { teams: [] };
  const teams = (table.teams || []).map((t) => t.name);
  const teamOptions = teams.map((n) => `<option value="${ucmlEsc(n)}">${ucmlEsc(n)}</option>`).join('');

  wrap.innerHTML = '';
  for (let i = 0; i < 4; i += 1) {
    const row = document.createElement('div');
    row.className = 'ucml-row';
    row.innerHTML = `
      <span class="ucml-rank">${i + 1}</span>
      <select class="ucml-team-sel"><option value="">选择队伍</option>${teamOptions}</select>
      <select class="ucml-player-sel" disabled><option value="">选择选手</option></select>
      <input class="ucml-score" type="number" step="100" value="25000">
      <span class="ucml-pt">—</span>`;
    wrap.appendChild(row);

    const teamSel = row.querySelector('.ucml-team-sel');
    const playerSel = row.querySelector('.ucml-player-sel');
    teamSel.addEventListener('change', () => {
      const list = d.players.filter((p) => p.team === teamSel.value);
      playerSel.innerHTML = '<option value="">选择选手</option>' +
        list.map((p) => `<option value="${ucmlEsc(p.name)}">${ucmlEsc(p.name)}</option>`).join('');
      playerSel.disabled = !list.length;
      if (list.length === 1) playerSel.value = list[0].name;
      ucmlRefreshTeams();
      ucmlClearPreview();
      ucmlUpdateSum();
    });
    playerSel.addEventListener('change', () => {
      ucmlClearPreview();
      ucmlUpdateSum();
    });
    row.querySelector('.ucml-score').addEventListener('input', () => {
      ucmlClearPreview();
      ucmlUpdateSum();
    });
  }
}

function ucmlRefreshTeams() {
  const rows = Array.from(document.querySelectorAll('#ucml-rows .ucml-row'));
  const chosen = rows.map((row) => row.querySelector('.ucml-team-sel').value).filter(Boolean);
  rows.forEach((row) => {
    const sel = row.querySelector('.ucml-team-sel');
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) return;
      opt.disabled = chosen.includes(opt.value) && opt.value !== sel.value;
    });
  });
}

function ucmlCollect() {
  return Array.from(document.querySelectorAll('#ucml-rows .ucml-row')).map((row) => ({
    team: row.querySelector('.ucml-team-sel').value,
    player: row.querySelector('.ucml-player-sel').value,
    score: parseInt(row.querySelector('.ucml-score').value, 10),
  }));
}

function ucmlUpdateSum() {
  const items = ucmlCollect();
  const sum = items.reduce((acc, it) => acc + (Number.isFinite(it.score) ? it.score : 0), 0);
  document.getElementById('ucml-sum').textContent = sum;
  const hint = document.getElementById('ucml-sum-hint');
  if (sum === 100000) {
    hint.textContent = '✓ 正好';
    hint.className = 'hint ok';
  } else if (sum > 100000) {
    hint.textContent = `超出 ${sum - 100000}`;
    hint.className = 'hint';
  } else {
    hint.textContent = `还差 ${100000 - sum}`;
    hint.className = 'hint';
  }
}

function ucmlClearPreview() {
  document.querySelectorAll('#ucml-rows .ucml-row').forEach((row) => {
    const pt = row.querySelector('.ucml-pt');
    pt.textContent = '—';
    pt.className = 'ucml-pt';
    row.style.background = '';
  });
}

function ucmlFormIssue(items) {
  if (items.some((it) => !it.team)) return '请为 4 行都选择队伍';
  if (items.some((it) => !it.player)) return '请为 4 行都选择选手';
  if (new Set(items.map((it) => it.player)).size !== 4) return '同一场比赛不能重复出现同一选手';
  if (new Set(items.map((it) => it.team)).size !== 4) return '同一队伍不能有两名选手同时出场';
  const sum = items.reduce((acc, it) => acc + (Number.isFinite(it.score) ? it.score : 0), 0);
  if (sum !== 100000) return `点数总和需要 100000（当前 ${sum}）`;
  return '';
}

async function ucmlPreview() {
  const items = ucmlCollect();
  const issue = ucmlFormIssue(items);
  if (issue) {
    ucmlSetMsg(issue, false);
    return;
  }
  const { status, data } = await api('/api/ucml/match/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ players: items.map((it) => it.player), scores: items.map((it) => it.score) }),
  });
  if (status !== 200 || !data.ok) {
    ucmlSetMsg((data && data.msg) || '预览失败喵', false);
    return;
  }
  const byName = {};
  data.entries.forEach((entry) => { byName[entry.player] = entry; });
  const rows = Array.from(document.querySelectorAll('#ucml-rows .ucml-row'));
  items.forEach((item, i) => {
    const entry = byName[item.player];
    if (!entry) return;
    const pt = rows[i].querySelector('.ucml-pt');
    pt.textContent = `${Number(entry.pt).toFixed(1)} pt`;
    pt.className = 'ucml-pt' + (entry.rank === 1 ? ' is-first' : '');
    rows[i].style.background = ucmlTint(entry);
  });
  ucmlSetMsg('预览完成，确认无误后点「记录比赛」', true);
}

async function ucmlSubmit() {
  const items = ucmlCollect();
  const issue = ucmlFormIssue(items);
  if (issue) {
    ucmlSetMsg(issue, false);
    return;
  }
  if (!confirm('确认记录这场比赛吗喵？')) return;
  const { status, data } = await api('/api/ucml/match/record', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ players: items.map((it) => it.player), scores: items.map((it) => it.score) }),
  });
  if (status !== 200 || !data.ok) {
    ucmlSetMsg((data && data.msg) || '记录失败喵', false);
    return;
  }
  ucmlSetMsg(`比赛记录成功，当前共 ${data.data.matches.length} 场喵`, true);
  ucmlState.formSig = '';
  ucmlApply(data.data, false);
}

// ---------- 排行榜 / 比赛记录 ----------

function ucmlTeamTable(rows, withInherit) {
  if (!rows.length) return '<p class="room-empty">当前阶段还没有队伍成绩喵</p>';
  const head = `<tr><th>名次</th><th>队伍</th><th>比赛</th><th>一位</th><th>二位</th><th>三位</th><th>四位</th>${withInherit ? '<th>继承pt</th>' : ''}<th>总pt</th></tr>`;
  const body = rows.map((row, i) => `
    <tr style="background:${ucmlTint(row)}">
      <td class="ucml-rank-cell">${i + 1}</td>
      <td>${ucmlTeamChip(row.name, row)}</td>
      <td>${row.match}</td>
      <td>${row.first}</td><td>${row.second}</td><td>${row.third}</td><td>${row.forth}</td>
      ${withInherit ? `<td>${Number(row.inherit || 0).toFixed(1)}</td>` : ''}
      <td class="ucml-pt-cell">${Number(row.score).toFixed(1)}</td>
    </tr>`).join('');
  return `<div class="ucml-table-wrap"><table class="ucml-table"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
}

function ucmlPlayerTable(rows) {
  if (!rows.length) return '<p class="room-empty">当前阶段还没有选手成绩喵</p>';
  const head = '<tr><th>名次</th><th>选手</th><th>队伍</th><th>比赛</th><th>一位</th><th>二位</th><th>三位</th><th>四位</th><th>总pt</th></tr>';
  const body = rows.map((row, i) => `
    <tr style="background:${ucmlTint(row)}">
      <td class="ucml-rank-cell">${i + 1}</td>
      <td class="ucml-player-cell">${ucmlEsc(row.name)}</td>
      <td>${ucmlTeamChip(row.team, row)}</td>
      <td>${row.match}</td>
      <td>${row.first}</td><td>${row.second}</td><td>${row.third}</td><td>${row.forth}</td>
      <td class="ucml-pt-cell">${Number(row.score).toFixed(1)}</td>
    </tr>`).join('');
  return `<div class="ucml-table-wrap"><table class="ucml-table"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
}

function renderUcmlStandings(d) {
  const seg = document.getElementById('ucml-rank-seg');
  const options = ucmlRankOptions();
  if (!options.includes(ucmlState.rankView)) ucmlState.rankView = options[0];
  seg.innerHTML = options.map((key) => (
    `<button class="seg-btn${key === ucmlState.rankView ? ' is-active' : ''}" data-rank="${key}" type="button">${UCML_RANK_LABELS[key]}</button>`
  )).join('');
  seg.querySelectorAll('[data-rank]').forEach((btn) => {
    btn.addEventListener('click', () => {
      ucmlState.rankView = btn.dataset.rank;
      renderUcmlStandings(d);
    });
  });

  const isTotal = ucmlState.rankView === 'total';
  const table = isTotal ? null : (d.stage_tables[ucmlState.rankView] || { teams: [], players: [] });
  const teams = isTotal ? d.total_teams : table.teams;
  const players = isTotal ? d.total_players : table.players;

  document.getElementById('ucml-rank-sub').textContent = isTotal
    ? `第 ${d.season} 赛季 · 全部阶段累计`
    : `第 ${d.season} 赛季 · ${UCML_RANK_LABELS[ucmlState.rankView]}（晋级的队伍含继承 pt）`;
  document.getElementById('ucml-standings').innerHTML =
    ucmlTeamTable(teams, !isTotal) + ucmlPlayerTable(players);
}

function renderUcmlMatches(d) {
  const seg = document.getElementById('ucml-match-seg');
  const options = [['all', '全部'], ['1', '常规赛'], ['2', '半决赛'], ['3', '决赛']];
  seg.innerHTML = options.map(([key, label]) => (
    `<button class="seg-btn${key === ucmlState.matchView ? ' is-active' : ''}" data-match="${key}" type="button">${label}</button>`
  )).join('');
  seg.querySelectorAll('[data-match]').forEach((btn) => {
    btn.addEventListener('click', () => {
      ucmlState.matchView = btn.dataset.match;
      renderUcmlMatches(d);
    });
  });

  const list = d.matches.filter((m) => ucmlState.matchView === 'all' || String(m.stage) === ucmlState.matchView);
  const box = document.getElementById('ucml-matches');
  if (!list.length) {
    box.innerHTML = '<p class="room-empty">还没有比赛记录喵</p>';
    return;
  }
  const head = '<tr><th>编号</th><th>阶段</th><th>一位</th><th>二位</th><th>三位</th><th>四位</th></tr>';
  const body = list.map((m) => {
    const cells = m.entries.map((entry) => `
      <td class="ucml-match-cell" style="background:${ucmlTint(entry)}">
        <div class="ucml-match-player">${ucmlEsc(entry.player)}</div>
        <div class="ucml-match-meta">${ucmlTeamChip(entry.team, entry)}<span class="ucml-match-pt">${Number(entry.pt).toFixed(1)}pt</span><span class="ucml-raw">${entry.raw == null ? '—' : entry.raw}</span></div>
      </td>`).join('');
    return `<tr><td class="ucml-rank-cell">${m.id}</td><td>${m.stage_name}</td>${cells}</tr>`;
  }).join('');
  box.innerHTML = `<div class="ucml-table-wrap"><table class="ucml-table ucml-match-table"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
}

// ---------- 队伍与选手 ----------

function ucmlHexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function renderUcmlRoster(d) {
  const box = document.getElementById('ucml-roster');
  const canTeamEdit = d.is_admin && d.stage === 0;
  const canPlayerEdit = d.is_admin && d.stage < 4;
  document.getElementById('ucml-roster-sub').textContent = d.archived
    ? '历史赛季阵容（只读）'
    : (d.stage === 0
      ? '准备期可以增删队伍与选手，开赛后阵容锁定'
      : '开赛后仍可补选手，已有比赛记录的选手不能移除');

  const byTeam = {};
  d.players.forEach((p) => {
    if (!byTeam[p.team]) byTeam[p.team] = [];
    byTeam[p.team].push(p.name);
  });

  const rows = d.teams.map((t) => {
    const names = byTeam[t.name] || [];
    const chips = names.length
      ? names.map((n) => `<span class="ucml-name-chip">${ucmlEsc(n)}${canPlayerEdit ? `<button class="ucml-x" data-del-player="${ucmlEsc(n)}" type="button" title="移除选手">×</button>` : ''}</span>`).join('')
      : '<span class="ucml-empty">暂无选手</span>';
    const del = canTeamEdit
      ? `<button class="btn btn-ghost btn-sm" data-del-team="${ucmlEsc(t.name)}" type="button">删除</button>`
      : '';
    return `<div class="ucml-roster-row">
      <div class="ucml-roster-team">${ucmlTeamChip(t.name, t)}<span class="ucml-count">${names.length} 人</span></div>
      <div class="ucml-roster-players">${chips}</div>
      ${del}
    </div>`;
  }).join('');

  let forms = '';
  if (canTeamEdit) {
    forms += `<div class="create-row ucml-add-row">
      <label class="field inline"><span>新队伍</span><input id="ucml-team-name" type="text" maxlength="16" placeholder="队名（≤16 字）"></label>
      <label class="field inline"><span>颜色</span><input id="ucml-team-color" type="color" value="#4f8cff"></label>
      <button class="btn btn-primary btn-sm" id="btn-ucml-add-team" type="button">添加队伍</button>
    </div>`;
  }
  if (canPlayerEdit && d.teams.length) {
    const rosterTeams = (d.stage >= 1 && d.stage <= 3)
      ? ((d.stage_tables[String(d.stage)] || { teams: d.teams }).teams || [])
      : d.teams;
    const opts = rosterTeams.map((t) => `<option value="${ucmlEsc(t.name)}">${ucmlEsc(t.name)}</option>`).join('');
    forms += `<div class="create-row ucml-add-row">
      <label class="field inline"><span>新选手</span><input id="ucml-player-name" type="text" maxlength="16" placeholder="选手名（≤16 字）"></label>
      <label class="field inline"><span>队伍</span><select id="ucml-player-team">${opts}</select></label>
      <button class="btn btn-primary btn-sm" id="btn-ucml-add-player" type="button">添加选手</button>
    </div>`;
  }

  box.innerHTML = (rows || '<p class="room-empty">还没有队伍喵</p>') + forms;

  box.querySelectorAll('[data-del-team]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!confirm(`确定删除队伍「${btn.dataset.delTeam}」及其全部选手吗喵？`)) return;
      ucmlPost('/api/ucml/team/delete', { name: btn.dataset.delTeam }, (data) => {
        ucmlSetMsg('队伍已删除喵', true);
        ucmlState.formSig = '';
        ucmlApply(data.data, false);
      });
    });
  });
  box.querySelectorAll('[data-del-player]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!confirm(`确定移除选手「${btn.dataset.delPlayer}」吗喵？`)) return;
      ucmlPost('/api/ucml/player/delete', { name: btn.dataset.delPlayer }, (data) => {
        ucmlSetMsg('选手已移除喵', true);
        ucmlState.formSig = '';
        ucmlApply(data.data, false);
      });
    });
  });

  const addTeam = document.getElementById('btn-ucml-add-team');
  if (addTeam) {
    addTeam.addEventListener('click', () => {
      const name = document.getElementById('ucml-team-name').value.trim();
      const color = ucmlHexToRgb(document.getElementById('ucml-team-color').value);
      if (!name) { ucmlSetMsg('请填写队名喵', false); return; }
      if (!color) { ucmlSetMsg('颜色格式不正确喵', false); return; }
      ucmlPost('/api/ucml/team/add', { name: name, color: color }, (data) => {
        ucmlSetMsg(`已添加队伍「${name}」喵`, true);
        ucmlApply(data.data, false);
      });
    });
  }

  const addPlayer = document.getElementById('btn-ucml-add-player');
  if (addPlayer) {
    addPlayer.addEventListener('click', () => {
      const name = document.getElementById('ucml-player-name').value.trim();
      const team = document.getElementById('ucml-player-team').value;
      if (!name) { ucmlSetMsg('请填写选手名喵', false); return; }
      ucmlPost('/api/ucml/player/add', { name: name, team: team }, (data) => {
        ucmlSetMsg(`已添加选手「${name}」喵`, true);
        ucmlState.formSig = '';
        ucmlApply(data.data, false);
      });
    });
  }
}

document.getElementById('btn-ucml-fill').addEventListener('click', () => {
  document.querySelectorAll('#ucml-rows .ucml-score').forEach((input) => { input.value = 25000; });
  ucmlClearPreview();
  ucmlUpdateSum();
});
document.getElementById('btn-ucml-preview').addEventListener('click', ucmlPreview);
document.getElementById('btn-ucml-submit').addEventListener('click', ucmlSubmit);

// ==================== 再来一局（沿用原配置与原班人马） ====================

function rematchButton(game, visible) {
  return visible
    ? `<button class="btn btn-primary btn-sm rematch-btn" data-game="${game}" type="button">再来一局</button>`
    : '';
}

function bindRematch(container, game, handler) {
  const btn = container.querySelector(`.rematch-btn[data-game="${game}"]`);
  if (btn) btn.addEventListener('click', handler);
}

async function rematchGame(endpoint, code, toast, enter) {
  if (!code) return;
  const { status, data } = await api(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  });
  if (status === 200 && data.ok) enter(data.code);
  else toast(data.msg || '再来一局失败喵');
}

function rematchFk() { return rematchGame('/api/farkle/rematch', fkCode, fkMsg, enterRoom); }
function rematchYz() { return rematchGame('/api/yahtzee/rematch', yzCode, yzMsg, enterYzRoom); }
function rematchMj() { return rematchGame('/api/mahjong17/rematch', mjCode, mjMsg, enterMjRoom); }
function rematchGold() { return rematchGame('/api/mahjong_gold/rematch', goldCode, goldMsg, enterGoldRoom); }

// ==================== 房间发言（对局双方 + 观众） ====================

const chatSigs = { fk: '', yz: '', mj: '', gold: '' };

function clearChatDom(prefix) {
  const list = document.getElementById(prefix + '-chat-list');
  if (list) list.innerHTML = '';
}

function setupFloatChat(prefix) {
  const card = document.getElementById(prefix + '-chat');
  if (!card || card.dataset.floatReady) return;
  card.dataset.floatReady = '1';
  const head = card.querySelector('.panel-head');
  if (!head) return;
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn btn-ghost btn-sm chat-collapse';
  btn.textContent = '收起';
  head.appendChild(btn);
  btn.addEventListener('click', (event) => {
    event.stopPropagation();
    const collapsed = card.classList.toggle('collapsed');
    btn.textContent = collapsed ? '展开' : '收起';
  });

  let drag = null;
  head.addEventListener('pointerdown', (event) => {
    if (event.target.closest('button')) return;
    const rect = card.getBoundingClientRect();
    drag = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, w: rect.width };
    head.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  head.addEventListener('pointermove', (event) => {
    if (!drag) return;
    const w = Math.min(drag.w, window.innerWidth - 16);
    const nx = Math.min(Math.max(8, drag.left + event.clientX - drag.x),
                        window.innerWidth - w - 8);
    const ny = Math.min(Math.max(8, drag.top + event.clientY - drag.y),
                        window.innerHeight - 56);
    card.style.left = nx + 'px';
    card.style.top = ny + 'px';
    card.style.right = 'auto';
    card.style.bottom = 'auto';
  });
  const stopDrag = () => { drag = null; };
  head.addEventListener('pointerup', stopDrag);
  head.addEventListener('pointercancel', stopDrag);
}

function showChat(prefix) {
  chatSigs[prefix] = '';
  clearChatDom(prefix);   // 换房间时先清掉上一间的残留消息
  const card = document.getElementById(prefix + '-chat');
  if (card) {
    setupFloatChat(prefix);
    card.classList.remove('hidden');
  }
}

function hideChat(prefix) {
  chatSigs[prefix] = '';
  clearChatDom(prefix);
  const card = document.getElementById(prefix + '-chat');
  if (card) card.classList.add('hidden');
}

function chatTime(ts) {
  const d = new Date((ts || 0) * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return pad(d.getHours()) + ':' + pad(d.getMinutes());
}

function renderChat(prefix, chat) {
  const list = document.getElementById(prefix + '-chat-list');
  if (!list) return;
  const items = chat || [];
  const sig = items.map((m) => m.time + ':' + m.name + ':' + m.text).join('|');
  if (sig === chatSigs[prefix]) return;
  chatSigs[prefix] = sig;
  list.innerHTML = '';
  if (!items.length) {
    const p = document.createElement('p');
    p.className = 'room-empty';
    p.textContent = '还没有人发言喵';
    list.appendChild(p);
    return;
  }
  items.forEach((m) => {
    const row = document.createElement('div');
    row.className = 'chat-row';
    const name = document.createElement('span');
    name.className = 'chat-name';
    name.textContent = m.name || '玩家';
    const text = document.createElement('span');
    text.className = 'chat-text';
    text.textContent = m.text || '';
    const time = document.createElement('span');
    time.className = 'chat-time';
    time.textContent = chatTime(m.time);
    row.appendChild(name);
    row.appendChild(text);
    row.appendChild(time);
    list.appendChild(row);
  });
  list.scrollTop = list.scrollHeight;
}

function wireChat(prefix, endpoint, getCode, toast) {
  const form = document.getElementById(prefix + '-chat-form');
  const input = document.getElementById(prefix + '-chat-input');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    const code = getCode();
    if (!text || !code) return;
    const { status, data } = await api(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code, text: text }),
    });
    if (status !== 200 || !data.ok) { toast(data.msg || '发言失败喵'); return; }
    input.value = '';
    renderChat(prefix, data.room && data.room.chat);
  });
}

wireChat('fk', '/api/farkle/say', () => fkCode, fkMsg);
wireChat('yz', '/api/yahtzee/say', () => yzCode, yzMsg);
wireChat('mj', '/api/mahjong17/say', () => mjCode, mjMsg);
wireChat('gold', '/api/mahjong_gold/say', () => goldCode, goldMsg);

// ==================== 顶部导航（喵喵远征队 / 小游戏 / 个人 / 开发中 / 管理） ====================

const mainNav = document.getElementById('main-nav');
const TAB_NAMES = ['expedition', 'games', 'stock', 'tournament', 'ucml', 'profile', 'dev', 'admin'];
let currentTab = 'expedition';

function showTabNav() {
  mainNav.classList.remove('hidden');
}

function closeGamePanels() {
  [fkLobbyTimer, yzLobbyTimer, mjLobbyTimer, goldLobbyTimer,
    fkRoomTimer, yzRoomTimer, mjRoomTimer, goldRoomTimer]
    .forEach((t) => clearInterval(t));
  fkLobbyTimer = null;
  yzLobbyTimer = null;
  mjLobbyTimer = null;
  goldLobbyTimer = null;
  fkRoomTimer = null;
  yzRoomTimer = null;
  mjRoomTimer = null;
  goldRoomTimer = null;
  fkPanel.classList.add('hidden');
  yzPanel.classList.add('hidden');
  mjPanel.classList.add('hidden');
  goldPanel.classList.add('hidden');
  hideChat('fk');
  hideChat('yz');
  hideChat('mj');
  hideChat('gold');
  homePanel.classList.remove('hidden');
}

function switchTab(name) {
  closeGamePanels();
  currentTab = name;
  mainNav.querySelectorAll('.nav-tab').forEach((b) => {
    b.classList.toggle('is-active', b.dataset.tab === name);
  });
  TAB_NAMES.forEach((k) => {
    document.getElementById('tab-' + k).classList.toggle('hidden', k !== name);
  });
  if (name === 'tournament') startTournamentPolling();
  else stopTournamentPolling();
  if (name === 'expedition') switchSub(currentSub);
  if (name === 'stock') loadStock();
  if (name === 'ucml') loadUcml();
  if (name === 'profile') loadProfile();
}

mainNav.addEventListener('click', (event) => {
  const btn = event.target.closest('.nav-tab');
  if (btn) switchTab(btn.dataset.tab);
});

// ==================== 喵喵远征队 · 子页（远征 / 远征队 / 图鉴 / 绘图） ====================

const subtabsEl = document.querySelector('.subtabs');
const SUB_NAMES = ['expedition', 'team', 'pedia', 'art'];
let currentSub = 'expedition';

function switchSub(name) {
  currentSub = name;
  subtabsEl.querySelectorAll('.subtab').forEach((b) => {
    b.classList.toggle('is-active', b.dataset.sub === name);
  });
  SUB_NAMES.forEach((k) => {
    document.getElementById('sub-' + k).classList.toggle('hidden', k !== name);
  });
  if (name === 'expedition') loadExpedition();
  if (name === 'team') loadTeam();
  if (name === 'pedia') loadPedia();
  if (name === 'art') loadArt();
}

subtabsEl.addEventListener('click', (event) => {
  const btn = event.target.closest('.subtab');
  if (btn) switchSub(btn.dataset.sub);
});

function afterShowHome() {
  showTabNav();
  switchTab(currentTab);
}

function portraitUrl(name) {
  return name ? '/catexp/cats/thumb/' + encodeURIComponent(name) + '.webp' : '';
}
function portraitFallback(name) {
  return name ? '/catexp/cats/' + encodeURIComponent(name) + '.png' : '';
}

function originUrl(name) {
  return name ? '/catexp/origins/thumb/' + encodeURIComponent(name) + '.webp' : '';
}
function originFallback(name) {
  return name ? '/catexp/origins/' + encodeURIComponent(name) + '.png' : '';
}

function artUrl(name, dir) {
  return name ? '/catexp/' + dir + '/large/' + encodeURIComponent(name) + '.webp' : '';
}
function artFallback(name, dir) {
  return name ? '/catexp/' + dir + '/' + encodeURIComponent(name) + '.png' : '';
}

function attrImg(cls, url, alt, fallback) {
  if (!url) return '';
  const fb = fallback ? ` onerror="this.onerror=null;this.src='${esc(fallback)}'"` : '';
  return `<img class="${cls}" src="${url}" alt="${esc(alt)}" loading="lazy"${fb}>`;
}

// ---------- 远征 ----------

const expTitle = document.getElementById('exp-title');
const expSub = document.getElementById('exp-sub');
const expStory = document.getElementById('exp-story');
const expBoss = document.getElementById('exp-boss');
const expHpText = document.getElementById('exp-hp-text');
const expHpFill = document.getElementById('exp-hp-fill');
const expMeta = document.getElementById('exp-meta');
const expRewards = document.getElementById('exp-rewards');
const expRank = document.getElementById('exp-rank');
const expMsgEl = document.getElementById('exp-msg');
const btnExpRun = document.getElementById('btn-exp-run');

function expSetMsg(text) {
  expMsgEl.textContent = text || '';
}

function rewardText(r) {
  return `🐟${r.fish} 💎${r.eye}`;
}

async function loadExpedition() {
  expSetMsg('');
  const { status, data } = await api('/api/expedition/state');
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) { expSetMsg(data.msg || '读取远征状态失败喵'); return; }
  renderExpedition(data.state);
  loadSummonPools();
  loadInsurance();
}

function renderExpedition(s) {
  expTitle.textContent = `${s.act_name} · 第 ${s.stage} 关`;
  expSub.textContent = `地形：${s.terrain}`;
  expBoss.textContent = `Boss：${s.boss_name}`;

  const story = s.boss_text || s.story_text;
  expStory.classList.toggle('hidden', !story);
  expStory.textContent = story || '';

  if (s.hidden) {
    expHpText.textContent = '血量：???';
    expHpFill.style.width = '100%';
    expHpFill.classList.add('unknown');
  } else {
    expHpText.textContent = `血量：${s.boss_hp} / ${s.boss_max}（${s.percent}%）`;
    expHpFill.style.width = `${Math.max(0, Math.min(100, s.percent))}%`;
    expHpFill.classList.remove('unknown');
  }

  expMeta.textContent = s.ran_today ? '你今天已经远征过了，明天再来喵' : '你还没远征，点右上角「远征」出手';

  const rw = s.rewards;
  expRewards.innerHTML = `
    <div class="exp-rw-row"><span class="exp-rw-tag">通关奖励（全员）</span>${rewardText(rw.clear)}</div>
    ${rw.top.map((t) => `<div class="exp-rw-row"><span class="exp-rw-tag">第${t.rank}名</span>${rewardText(t)}</div>`).join('')}
    <div class="exp-rw-row"><span class="exp-rw-tag">最后一击</span>${rewardText(rw.last_hit)}</div>`;

  if (s.hidden) {
    expRank.innerHTML = '<p class="room-empty">Boss 血量已低于 25%，伤害排行暂不公开喵</p>';
  } else if (!s.ranking.length) {
    expRank.innerHTML = '<p class="room-empty">还没有人出手喵</p>';
  } else {
    expRank.innerHTML = s.ranking.map((r, i) => `
      <div class="rank-row">
        <span class="rank-no">${i + 1}</span>
        <span class="rank-name">${esc(r.name)}</span>
        <span class="rank-val">${r.damage}</span>
      </div>`).join('');
  }

  btnExpRun.disabled = !!s.ran_today;
  btnExpRun.textContent = s.ran_today ? '今日已远征' : '远征';
  renderWallet(s);
}

btnExpRun.addEventListener('click', async () => {
  btnExpRun.disabled = true;
  expSetMsg('远征中…');
  const { status, data } = await api('/api/expedition/run', { method: 'POST' });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    expSetMsg(data.msg || '远征失败喵');
    btnExpRun.disabled = false;
    return;
  }
  expSetMsg('');
  document.getElementById('exp-result-card').classList.remove('hidden');
  document.getElementById('exp-result').textContent = (data.lines || []).join('\n');
  if (data.state) renderExpedition(data.state);
  refresh();   // 鱼干/猫眼石可能变化，顺带刷新顶部属性
});

// ---------- 签到 / 抽卡 ----------

const walletSub = document.getElementById('wallet-sub');
const btnSignin = document.getElementById('btn-signin');
const summonCount = document.getElementById('summon-count');
const summonPool = document.getElementById('summon-pool');
const btnSummon = document.getElementById('btn-summon');
const summonHint = document.getElementById('summon-hint');
const summonMsg = document.getElementById('summon-msg');
const summonResult = document.getElementById('summon-result');

let summonCost = 100;

function setSummonMsg(text, ok) {
  summonMsg.textContent = text || '';
  summonMsg.className = ok ? 'msg ok' : 'msg';
}

function updateSummonHint() {
  const n = Math.max(1, Number(summonCount.value) || 1);
  summonHint.textContent = `单抽 ${summonCost} 鱼干，本次需 ${n * summonCost} 鱼干`;
}

function renderWallet(s) {
  summonCost = s.summon_cost;
  walletSub.textContent = `鱼干 ${s.fish} | 猫眼石 ${s.eye_stones} | 今日签到：${s.signin_done ? '已签' : '未签'}`;
  btnSignin.disabled = !!s.signin_done;
  btnSignin.textContent = s.signin_done ? '今日已签' : '签到';
  updateSummonHint();
  renderInsurance(s.insurance);
}

async function loadSummonPools() {
  if (summonPool.dataset.filled === '1') return;
  const idx = await fetchCatIndex();
  if (!idx) return;
  summonPool.innerHTML = '<option value="全">全部卡池</option>'
    + idx.pools.filter((p) => p.key !== 'default')
      .map((p) => `<option value="${esc(p.key)}">${esc(p.name)}（${p.count} 张）</option>`).join('');
  summonPool.dataset.filled = '1';
}

summonCount.addEventListener('input', updateSummonHint);

btnSignin.addEventListener('click', async () => {
  btnSignin.disabled = true;
  setSummonMsg('签到中…', false);
  const { status, data } = await api('/api/cat/signin', { method: 'POST' });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    setSummonMsg(data.msg || '签到失败喵', false);
    btnSignin.disabled = false;
    return;
  }
  setSummonMsg((data.lines || []).join('　'), true);
  refresh();
});

btnSummon.addEventListener('click', async () => {
  const n = Math.max(1, Number(summonCount.value) || 1);
  btnSummon.disabled = true;
  setSummonMsg('抽卡中…', false);
  summonResult.innerHTML = '';
  const { status, data } = await api('/api/cat/summon', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count: n, pool: summonPool.value }),
  });
  btnSummon.disabled = false;
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    setSummonMsg(data.msg || '抽卡失败喵', false);
    return;
  }
  const head = `共 ${data.drawn.length} 只，消耗 ${data.cost} 鱼干`;
  const eventText = insuranceEventText(data.insurance_event);
  const payoutDrawn = (data.insurance_event && data.insurance_event.payout
    && data.insurance_event.payout.drawn) || [];
  const fullHead = data.lucky ? `✨ 欧气爆发！一抽变十连！${head}` : head;
  setSummonMsg(eventText ? `${fullHead}　${eventText}` : fullHead, true);
  renderSummonResult(data.drawn.concat(payoutDrawn));
  renderInsurance(data.insurance);
  refresh();
});

function insuranceEventText(event) {
  if (!event) return '';
  if (event.status === 'paid') return `🛡 保险赔付：${event.payout ? event.payout.text : ''}`;
  if (event.status === 'failed') {
    return `🛡 保单失效：第 ${event.order} 抽出现${rarityName(event.rarity)}「${event.name}」`;
  }
  if (event.status === 'skipped') return '🛡 欧气十连不消耗保单进度';
  if (event.status === 'active') return `🛡 保单进度 ${event.used}/${event.window}`;
  return '';
}

function renderSummonResult(drawn) {
  summonResult.innerHTML = drawn.map((r) => {
    let desc;
    if (r.refunded) desc = `已满星，返还 ${r.refund_amt} 鱼干`;
    else if (r.is_new) desc = '<span class="summon-new">新喵喵 · 已进队</span>';
    else {
      desc = `升到 ★${r.star}`;
      if (r.job_up) desc += `，转职为 ${esc(r.job)}`;
    }
    return `<div class="summon-row r-${r.rarity}">
      ${attrImg('summon-icon', portraitUrl(r.portrait), r.name, portraitFallback(r.portrait))}
      <div class="summon-info">
        <div class="summon-name">${esc(r.name)}
          <span class="summon-rarity">${esc(rarityName(r.rarity))}</span></div>
        <div class="summon-desc">${desc}</div>
      </div>
      <div class="summon-star">★${r.star}</div>
    </div>`;
  }).join('');
}

// ---------- 喵保险 ----------

const insStatus = document.getElementById('ins-status');
const insTiers = document.getElementById('ins-tiers');
const insMsg = document.getElementById('ins-msg');
let insTiersFilled = false;

function renderInsurance(ins) {
  if (!ins) {
    insStatus.textContent = '未购买 · 十抽全普通即赔付';
    return;
  }
  insStatus.textContent = `${ins.tier_name} 生效中 · 进度 ${ins.used}/${ins.window} · ${ins.payout_text}`;
}

async function loadInsurance() {
  const { status, data } = await api('/api/cat/insurance');
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  renderInsurance(data.insurance);
  if (insTiersFilled) return;
  insTiers.innerHTML = data.tiers.map((t) => {
    const cost = t.cost_fish ? `${t.cost_fish} 鱼干` : `${t.cost_eye} 猫眼石`;
    return `<button class="ins-btn" data-tier="${esc(t.key)}" type="button">
      <span class="ins-btn-name">${esc(t.name)}</span>
      <span class="ins-btn-cost">${esc(cost)}</span>
      <span class="ins-btn-pay">${esc(t.payout_text)}</span>
    </button>`;
  }).join('');
  insTiers.querySelectorAll('.ins-btn').forEach((btn) => {
    btn.addEventListener('click', () => buyInsurance(btn.dataset.tier));
  });
  insTiersFilled = true;
}

async function buyInsurance(tier) {
  insMsg.textContent = '购买中…';
  insMsg.className = 'msg';
  const { status, data } = await api('/api/cat/insurance/buy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tier }),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    insMsg.textContent = data.msg || '购买失败喵';
    return;
  }
  insMsg.textContent = `购买成功：${data.insurance.tier_name} 生效中`;
  insMsg.className = 'msg ok';
  renderInsurance(data.insurance);
  refresh();
}

// ---------- 远征队 ----------

const teamStats = document.getElementById('team-stats');
const teamCats = document.getElementById('team-cats');

async function loadTeam() {
  const { status, data } = await api('/api/cat/collection');
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  const t = data.team;
  const info = t.info;
  const rows = [
    ['喵喵', info.cats], ['满星', info.max_star], ['基础战力', info.base_power],
    ['鱼干', info.fish], ['猫眼石', info.eye_stones], ['遗物', info.relics],
    ['研究上限', info.research_limit], ['累计签到', info.signin_total],
    ['连续签到', info.signin_streak], ['累计抽喵', info.summon_count],
    ['远征次数', info.expedition_total], ['远征总伤害', info.expedition_damage],
  ];
  teamStats.innerHTML = rows.map(([label, val]) => `
    <div class="stat"><div class="stat-num">${val}</div><div class="stat-label">${label}</div></div>`).join('');

  if (!t.cats.length) {
    teamCats.innerHTML = '<p class="room-empty">还没有喵喵，去群里发「抽喵喵」抽几只吧</p>';
    return;
  }
  teamCats.innerHTML = t.cats.map((c) => {
    const photo = attrImg('cat-icon', portraitUrl(c.portrait), c.name, portraitFallback(c.portrait));
    return `<div class="cat-cell owned r-${c.rarity}" data-id="${esc(c.id)}">
      ${photo}
      <div class="cat-name">${esc(c.name)}</div>
      <div class="cat-tags"><span class="cat-star">★${c.star}</span>
        <span class="cat-job">${esc(c.job || '—')}</span></div>
      <div class="cat-sub">${esc(c.country_name)} · 战力 ${c.power}</div>
    </div>`;
  }).join('');
  bindCatCells(teamCats);
}

// ---------- 图鉴 ----------

let catIndexCache = null;
let pediaMode = 'country';

async function fetchCatIndex() {
  if (catIndexCache) return catIndexCache;
  const { status, data } = await api('/api/cat/index');
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return null; }
  if (status !== 200 || !data.ok) return null;
  catIndexCache = data.index;
  return catIndexCache;
}

const pediaBody = document.getElementById('pedia-body');
const pediaSub = document.getElementById('pedia-sub');
const pediaModes = document.getElementById('pedia-modes');

async function loadPedia() {
  const idx = await fetchCatIndex();
  if (!idx) return;
  pediaSub.textContent = `已收集 ${idx.owned_count} / ${idx.total_count}`;
  renderPedia();
}

pediaModes.addEventListener('click', (event) => {
  const btn = event.target.closest('.seg-btn');
  if (!btn || btn.dataset.mode === pediaMode) return;
  pediaMode = btn.dataset.mode;
  pediaModes.querySelectorAll('.seg-btn').forEach((b) => {
    b.classList.toggle('is-active', b.dataset.mode === pediaMode);
  });
  renderPedia();
});

function catCellHtml(cat) {
  const owned = cat.star > 0;
  if (!owned) {
    return `<div class="cat-cell unknown"><div class="cat-unknown">?</div>
      <div class="cat-name dim">？？？</div></div>`;
  }
  const photo = attrImg('cat-icon', portraitUrl(cat.portrait), cat.name, portraitFallback(cat.portrait));
  return `<div class="cat-cell owned r-${cat.rarity}" data-id="${esc(cat.id)}">
    ${photo}
    <div class="cat-name">${esc(cat.name)}</div>
    <div class="cat-tags"><span class="cat-star">★${cat.star}</span>
      <span class="cat-job">${esc(cat.job || '—')}</span></div>
    <div class="cat-sub">${esc(cat.trait)}</div>
  </div>`;
}

function bindCatCells(root) {
  root.querySelectorAll('.cat-cell.owned').forEach((el) => {
    el.addEventListener('click', () => openCatDetail(el.dataset.id));
  });
}

function renderPedia() {
  const idx = catIndexCache;
  if (!idx) return;
  const byId = {};
  idx.cats.forEach((c) => { byId[c.id] = c; });
  let html = '';

  if (pediaMode === 'country') {
    Object.keys(idx.countries).sort().forEach((code) => {
      const cats = idx.cats.filter((c) => c.country === code);
      if (!cats.length) return;
      const got = cats.filter((c) => c.star > 0).length;
      const name = idx.countries[code];
      html += `<div class="pedia-group">
        <div class="pedia-head">
          ${attrImg('pedia-flag', originUrl(name), name, originFallback(name))}
          <span class="pedia-title">${esc(name)}</span>
          <span class="pedia-progress">${got}/${cats.length}</span>
        </div>
        <div class="cat-grid">${cats.map(catCellHtml).join('')}</div>
      </div>`;
    });
  } else {
    idx.pools.forEach((p) => {
      const cats = p.ids.map((id) => byId[id]).filter(Boolean);
      const got = cats.filter((c) => c.star > 0).length;
      html += `<div class="pedia-group">
        <div class="pedia-head">
          <span class="pedia-title">${esc(p.name)}</span>
          <span class="pedia-progress">${got}/${cats.length}</span>
        </div>
        <div class="cat-grid">${cats.map(catCellHtml).join('')}</div>
      </div>`;
    });
  }
  pediaBody.innerHTML = html;
  bindCatCells(pediaBody);
}

// ---------- 绘图 ----------

const artCountry = document.getElementById('art-country');
const artMsg = document.getElementById('art-msg');
const artBookWrap = document.getElementById('art-book-wrap');
const artBook = document.getElementById('art-book');

async function loadArt() {
  const artMap = document.getElementById('art-map');
  artMap.onerror = () => { artMap.onerror = null; artMap.src = artFallback('地图', 'data'); };
  artMap.src = artUrl('地图', 'data');
  document.getElementById('art-acts').innerHTML = ['act1_story', 'act1_boss', 'act1_clear'].map((n) => {
    const label = { act1_story: '第一幕 · 剧情', act1_boss: '第一幕 · Boss', act1_clear: '第一幕 · 通关' }[n];
    return `<figure class="art-fig">
      <img class="art-img" src="${artUrl(n, 'expedition')}" alt="${esc(label)}" loading="lazy"
           onerror="this.onerror=null;this.src='${esc(artFallback(n, 'expedition'))}'">
      <figcaption>${esc(label)}</figcaption>
    </figure>`;
  }).join('');

  const idx = await fetchCatIndex();
  if (!idx || artCountry.options.length) return;
  Object.keys(idx.countries).sort().forEach((code) => {
    const opt = document.createElement('option');
    opt.value = code;
    opt.textContent = `${code} ${idx.countries[code]}`;
    artCountry.appendChild(opt);
  });
}

document.getElementById('btn-art-book').addEventListener('click', () => {
  const code = artCountry.value;
  if (!code) { artMsg.textContent = '先选一个国家喵'; return; }
  artMsg.textContent = '生成中…';
  artBookWrap.classList.remove('hidden');
  artBook.onload = () => { artMsg.textContent = ''; };
  artBook.onerror = () => { artMsg.textContent = '图鉴生成失败喵'; };
  artBook.src = `/api/cat/book?code=${encodeURIComponent(code)}&t=${Date.now()}`;
});

// ---------- 喵喵详情弹层 ----------

const catModal = document.getElementById('cat-modal');
const catModalBody = document.getElementById('cat-modal-body');

function closeCatModal() {
  catModal.classList.add('hidden');
  catModalBody.innerHTML = '';
}

document.getElementById('cat-modal-close').addEventListener('click', closeCatModal);
document.getElementById('cat-modal-mask').addEventListener('click', closeCatModal);

async function openCatDetail(id) {
  const { status, data } = await api('/api/cat/detail?id=' + encodeURIComponent(id));
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  const c = data.cat;
  const poolName = poolNameOf(c.pool);
  const photo = attrImg('detail-icon', portraitUrl(c.portrait), c.name, portraitFallback(c.portrait));
  catModalBody.innerHTML = `
    <div class="detail-top">
      ${photo}
      <div class="detail-head">
        <div class="detail-name r-${c.rarity}">${esc(c.name)}
          <span class="detail-star">${c.owned ? '★' + c.star : '未解锁'}</span></div>
        <div class="detail-line">${esc(c.id)} · ${esc(c.country_name)}${poolName ? ' · ' + esc(poolName) : ''}</div>
      </div>
      ${attrImg('detail-flag', originUrl(c.country_name), c.country_name, originFallback(c.country_name))}
    </div>
    <div class="detail-rows">
      <div><span>职业</span>${esc(c.job || '—')}</div>
      <div><span>稀有度</span>${esc(rarityName(c.rarity))}</div>
      <div><span>适性</span>${esc(c.trait)}</div>
      <div><span>成长路线</span>${esc((c.job_path || []).join(' → ') || '—')}</div>
    </div>
    <p class="detail-intro">${esc(c.intro || '')}</p>
    ${c.owned ? `<div class="detail-card-wrap"><div class="detail-card-label">队员卡片（绘图）</div>
      <img id="detail-card-img" class="art-img" alt="${esc(c.name)}" loading="lazy"></div>` : ''}`;
  catModal.classList.remove('hidden');

  const img = document.getElementById('detail-card-img');
  if (img) img.src = `/api/cat/card?id=${encodeURIComponent(c.id)}`;
}

function poolNameOf(key) {
  if (!catIndexCache || !key) return '';
  const p = catIndexCache.pools.find((x) => x.key === key);
  return p ? p.name : '';
}

function rarityName(r) {
  return { normal: '普通', rare: '稀有', epic: '史诗', legend: '传说' }[r] || r;
}

// ---------- 每周挑战 · 快艇骰子 ----------

const weeklyRanks = document.getElementById('weekly-ranks');
const weeklySub = document.getElementById('weekly-sub');

async function loadWeekly() {
  const { status, data } = await api('/api/yahtzee/weekly');
  if (status === 401) { yzPanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  weeklySub.textContent = `本周（${data.week}）排行依据：${data.basis}；满 ${data.max_games} 局才算数领奖，同分并列领同一档（取高不取低）`;
  if (!data.ranks.length && !(data.rest || []).length) {
    weeklyRanks.innerHTML = '<p class="room-empty">本周还没有人完成对局喵，去开一局吧</p>';
    return;
  }
  const rows = data.ranks.map((r) => `
    <div class="rank-row">
      <span class="rank-no">${r.rank}</span>
      <span class="rank-name">${esc(r.name)}</span>
      <span class="rank-val">平均 ${r.score} 分（${r.played}/${data.max_games} 局）</span>
      <span class="rank-reward">奖励 ${r.reward} 鱼干</span>
    </div>`).join('');
  const restRows = (data.rest || []).map((r) => `
    <div class="rank-row">
      <span class="rank-no">—</span>
      <span class="rank-name">${esc(r.name)}</span>
      <span class="rank-val">平均 ${r.score} 分（${r.played}/${data.max_games} 局）</span>
      <span class="rank-reward">不满 ${data.max_games} 局，不领奖</span>
    </div>`).join('');
  const restBlock = restRows
    ? `<p class="hint">本周不满 ${data.max_games} 局（不参与领奖）</p>${restRows}`
    : '';
  weeklyRanks.innerHTML = (rows || `<p class="room-empty">本周还没有人打满 ${data.max_games} 局喵</p>`) + restBlock;
}

document.getElementById('btn-weekly-refresh').addEventListener('click', loadWeekly);

// ---------- 个人页面 ----------

const profileInfo = document.getElementById('profile-info');
const nickInput = document.getElementById('nick-input');
const nickMsg = document.getElementById('nick-msg');

async function loadProfile() {
  const { status, data } = await api('/api/me');
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) return;
  const p = data.player;
  const rows = [
    ['QQ', p.qq], ['昵称', p.nick || '（未设置）'], ['身份', p.is_admin ? '管理员' : '普通玩家'],
    ['鱼干', p.fish], ['猫眼石', p.eye_stones], ['喵喵', p.cats],
    ['抽喵次数', p.summon_count], ['累计签到', p.signin_total],
  ];
  profileInfo.innerHTML = rows.map(([label, val]) => `
    <div class="stat"><div class="stat-num">${esc(val)}</div><div class="stat-label">${label}</div></div>`).join('');
  nickInput.value = p.nick || '';
}

document.getElementById('nick-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const nick = nickInput.value.trim();
  nickMsg.textContent = '';
  nickMsg.classList.remove('ok');
  const { status, data } = await api('/api/profile/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nick }),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    nickMsg.textContent = data.msg || '改名失败喵';
    return;
  }
  nickMsg.textContent = data.msg || '改名成功喵';
  nickMsg.classList.add('ok');
  await refresh();   // 顶部玩家昵称与个人信息一起刷新
});

// ---------- 赠送 ----------

const giftMsg = document.getElementById('gift-msg');
const giftTarget = document.getElementById('gift-target');
const giftAmount = document.getElementById('gift-amount');
const giftKind = document.getElementById('gift-kind');

document.getElementById('gift-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  giftMsg.textContent = '';
  giftMsg.classList.remove('ok');
  const target = giftTarget.value.trim();
  const amount = giftAmount.value.trim();
  if (!target || !amount) {
    giftMsg.textContent = '对方 QQ 和数量都要填喵';
    return;
  }
  const { status, data } = await api('/api/gift', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target, amount, kind: giftKind.value }),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    giftMsg.textContent = data.msg || '赠送失败喵';
    return;
  }
  giftMsg.textContent = `${data.msg}（对方余额：${data.target_balance}）`;
  giftMsg.classList.add('ok');
  giftAmount.value = '';
  await refresh();       // 顶部余额与个人信息一起刷新
  await loadProfile();
});

// ---------- 管理员页面（仅管理员可见） ----------

document.getElementById('admin-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const qq = document.getElementById('admin-qq').value.trim();
  const nick = document.getElementById('admin-nick').value.trim();
  const msg = document.getElementById('admin-msg');
  msg.textContent = '';
  msg.classList.remove('ok');
  const { status, data } = await api('/api/admin/create_user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ qq, nick }),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    msg.textContent = data.msg || '创建失败喵';
    return;
  }
  msg.textContent = data.msg || '创建成功喵';
  msg.classList.add('ok');
  event.target.reset();
});

// ==================== 锦标赛 ====================

const tourList = document.getElementById('tour-list');
const tourMsgEl = document.getElementById('tour-msg');
const tourCreateBox = document.getElementById('tour-create');
const tourCreateMsg = document.getElementById('tour-create-msg');
const tourProjectsBox = document.getElementById('tour-projects');

let tourTimer = null;
let tourMsgTimer = null;
let tourProjectsBuilt = false;

function tourMsg(text, ok) {
  tourMsgEl.textContent = text || '';
  tourMsgEl.classList.toggle('ok', !!ok);
  clearTimeout(tourMsgTimer);
  if (text) tourMsgTimer = setTimeout(() => { tourMsgEl.textContent = ''; }, 4000);
}

function tourStatusText(s) {
  return { waiting: '报名中', playing: '进行中', done: '已结束' }[s] || s;
}

function buildTourProjects(data) {
  if (tourProjectsBuilt) return;
  tourProjectsBuilt = true;
  tourProjectsBox.innerHTML = data.projects.map((p) => (
    `<label class="chk"><input type="checkbox" value="${esc(p.key)}" checked> ${esc(p.name)}</label>`
  )).join('');
}

function renderTourRounds(t) {
  if (!t.rounds || !t.rounds.length) return '';
  const cols = t.rounds.map((rnd) => {
    const matches = rnd.matches.map((m) => {
      const aWin = m.winner_idx === 0 ? 'is-win' : '';
      const bWin = m.winner_idx === 1 ? 'is-win' : '';
      const sub = m.winner
        ? `胜者 ${esc(m.winner)}`
        : (m.active ? '进行中' : '待定');
      return `
        <div class="tour-match${m.active ? ' is-active' : ''}">
          <div class="tour-match-names">
            <span class="${aWin}">${esc(m.names[0])}</span>
            <span class="tour-vs">vs</span>
            <span class="${bWin}">${esc(m.names[1])}</span>
          </div>
          <div class="tour-match-sub">${esc(m.project)}${m.games > 1 ? ` · 已打 ${m.games} 局` : ''} · ${sub}</div>
          ${m.error ? `<div class="tour-match-error">${esc(m.error)}</div>` : ''}
        </div>`;
    }).join('');
    return `
      <div class="tour-round">
        <div class="tour-round-name">${esc(rnd.name)}</div>
        ${matches}
      </div>`;
  }).join('');
  return `<div class="tour-rounds">${cols}</div>`;
}

function renderTourCard(t, data) {
  const rewards = [];
  if (t.champion_fish) rewards.push(`冠军 ${t.champion_fish} 鱼干`);
  if (t.champion_stone) rewards.push(`冠军 ${t.champion_stone} 猫眼石`);
  const rewardText = rewards.length ? rewards.join(' + ') + '（其余名次对半递减）' : '无奖励';
  const poolText = t.pool.map((p) => p.name).join('、');
  const names = t.players.map((p) => esc(p.name)).join('、') || '还没有人报名';

  let acts = '';
  if (t.status === 'waiting') {
    if (t.joined) {
      acts += `<button class="btn btn-ghost btn-sm" data-tour-act="leave" data-code="${t.code}">退出报名</button>`;
    } else if (t.can_join) {
      acts += `<button class="btn btn-primary btn-sm" data-tour-act="join" data-code="${t.code}">报名</button>`;
    } else if (!t.full) {
      acts += '<span class="hint">你已在另一场锦标赛中</span>';
    }
    if (t.full) {
      acts += `<button class="btn btn-primary btn-sm" data-tour-act="start" data-code="${t.code}">开始比赛</button>`;
    }
    if (t.is_owner || data.is_admin) {
      acts += `<button class="btn btn-ghost btn-sm" data-tour-act="cancel" data-code="${t.code}">取消</button>`;
    }
  } else if (t.status === 'playing' && data.is_admin) {
    acts += `<button class="btn btn-ghost btn-sm" data-tour-act="force_end" data-code="${t.code}">强制结束</button>`;
  }

  let mine = '';
  if (t.my_match) {
    const m = t.my_match;
    const label = `${esc(m.project)} · ${esc(m.names[0])} vs ${esc(m.names[1])}`;
    mine = m.room
      ? `<div class="tour-mine">你的对局：${label}
          <button class="btn btn-primary btn-sm" data-tour-act="enter" data-key="${esc(m.key)}" data-room="${esc(m.room)}">进入对局</button>
        </div>`
      : `<div class="tour-mine">你的对局：${label} —— 正在开局${m.error ? `（${esc(m.error)}）` : '…'}</div>`;
  }

  const doneBlock = t.status === 'done'
    ? `<div class="tour-champion">🏆 冠军：${esc(t.champion || '—')}</div>
       ${t.reward_lines.length ? `<pre class="tour-reward-lines">${t.reward_lines.map(esc).join('\n')}</pre>` : ''}`
    : '';

  return `
    <div class="card tour-card">
      <div class="panel-head">
        <div>
          <div class="panel-title">${t.size} 人锦标赛 · ${tourStatusText(t.status)}
            <span class="tour-code">${esc(t.code)}</span></div>
          <div class="panel-sub">项目：${esc(poolText)}｜${esc(rewardText)}</div>
        </div>
        <div class="tour-actions">${acts}</div>
      </div>
      <div class="tour-players">报名 ${t.players.length}/${t.size}：${names}</div>
      ${mine}
      ${doneBlock}
      ${renderTourRounds(t)}
    </div>`;
}

function renderTournament(data) {
  tourCreateBox.classList.toggle('hidden', !data.is_admin);
  document.getElementById('tour-reward-hint').textContent = data.reward_admin
    ? '可以设置冠军鱼干 / 猫眼石奖励，其余名次按对半递减'
    : '当前账号不能设置奖励（带奖励的锦标赛仅指定管理员可以开放）';
  const fishInput = document.getElementById('tour-fish');
  const stoneInput = document.getElementById('tour-stone');
  fishInput.disabled = !data.reward_admin;
  stoneInput.disabled = !data.reward_admin;
  if (!data.reward_admin) { fishInput.value = '0'; stoneInput.value = '0'; }
  buildTourProjects(data);

  if (!data.list.length) {
    tourList.innerHTML = '<div class="card"><p class="room-empty">还没有锦标赛喵，等管理员开一场吧</p></div>';
    return;
  }
  tourList.innerHTML = data.list.map((t) => renderTourCard(t, data)).join('');
}

function updateTournamentNotice(data) {
  const btn = mainNav.querySelector('.nav-tab[data-tab="tournament"]');
  if (!btn) return;
  const mine = (data.list || []).find((t) => t.my_match && t.my_match.room);
  btn.classList.toggle('has-notice', !!mine);
}

async function loadTournament() {
  const { status, data } = await api('/api/tournament/state');
  if (status === 401) {
    stopTournamentPolling();
    homePanel.classList.add('hidden');
    showLogin();
    return;
  }
  if (status !== 200 || !data.ok) return;
  renderTournament(data);
  updateTournamentNotice(data);
}

function startTournamentPolling() {
  loadTournament();
  clearInterval(tourTimer);
  tourTimer = setInterval(loadTournament, 2000);
}

function stopTournamentPolling() {
  if (tourTimer) {
    clearInterval(tourTimer);
    tourTimer = null;
  }
}

async function tournamentAct(act, code) {
  if (!code) return;
  const { status, data } = await api('/api/tournament/' + act, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) { tourMsg(data.msg || '操作失败喵'); return; }
  await loadTournament();
}

async function createTournament() {
  tourCreateMsg.textContent = '';
  tourCreateMsg.classList.remove('ok');
  const projects = Array.from(tourProjectsBox.querySelectorAll('input:checked'))
    .map((i) => i.value);
  if (!projects.length) {
    tourCreateMsg.textContent = '至少选一个比赛项目喵';
    return;
  }
  const body = {
    size: document.getElementById('tour-size').value,
    projects: projects,
    champion_fish: document.getElementById('tour-fish').value || 0,
    champion_stone: document.getElementById('tour-stone').value || 0,
  };
  const { status, data } = await api('/api/tournament/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    tourCreateMsg.textContent = data.msg || '创建失败喵';
    return;
  }
  tourCreateMsg.textContent = '创建成功喵，把编号发给对手报名吧';
  tourCreateMsg.classList.add('ok');
  await loadTournament();
}

async function enterTournamentMatch(key, room) {
  if (!room) return;
  currentTab = 'tournament';
  stopTournamentPolling();
  loginPanel.classList.add('hidden');
  pwdPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
  if (key === 'yahtzee') {
    yzPanel.classList.remove('hidden');
    await enterYzRoom(room);
  } else if (key === 'farkle') {
    fkPanel.classList.remove('hidden');
    await enterRoom(room);
  } else if (key === 'mahjong17') {
    mjPanel.classList.remove('hidden');
    await enterMjRoom(room);
  } else if (key === 'mahjong_gold') {
    goldPanel.classList.remove('hidden');
    await enterGoldRoom(room);
  } else {
    tourMsg('未知的比赛项目喵');
  }
}

document.getElementById('btn-tour-refresh').addEventListener('click', () => loadTournament());
document.getElementById('btn-tour-create').addEventListener('click', createTournament);

tourList.addEventListener('click', async (event) => {
  const btn = event.target.closest('button[data-tour-act]');
  if (!btn) return;
  const act = btn.dataset.tourAct;
  if (act === 'enter') {
    enterTournamentMatch(btn.dataset.key, btn.dataset.room);
    return;
  }
  await tournamentAct(act, btn.dataset.code);
});

// 不在锦标赛页时也低频检查一下自己有没有待进的对局，给导航加红点
setInterval(async () => {
  if (tourTimer || homePanel.classList.contains('hidden')) return;
  const { status, data } = await api('/api/tournament/state');
  if (status === 200 && data.ok) updateTournamentNotice(data);
}, 6000);

// ==================== 喵股市 ====================

const stockStatusEl = document.getElementById('stock-status');
const stockWalletEl = document.getElementById('stock-wallet');
const stockRulesEl = document.getElementById('stock-rules');
const stockExchangeEl = document.getElementById('stock-exchange-hint');
const stockMsgEl = document.getElementById('stock-msg');
const stockCodesEl = document.getElementById('stock-codes');
const stockCodeEl = document.getElementById('stock-code');
const stockSharesEl = document.getElementById('stock-shares');
const stockFishEl = document.getElementById('stock-fish-amount');
const stockMarketBodyEl = document.getElementById('stock-market-body');
const stockMarketSubEl = document.getElementById('stock-market-sub');
const stockHoldingsEl = document.getElementById('stock-holdings');
const stockHoldSubEl = document.getElementById('stock-hold-sub');
const stockRankSubEl = document.getElementById('stock-rank-sub');
const stockRankBestEl = document.getElementById('stock-rank-best');
const stockRankWorstEl = document.getElementById('stock-rank-worst');
const stockNewsEl = document.getElementById('stock-news');

function stockMoney(n) {
  return Number(n || 0).toLocaleString('zh-CN');
}

function stockPnlCell(n) {
  const v = Number(n || 0);
  return `<td class="${v >= 0 ? 'stock-up' : 'stock-down'}">${v >= 0 ? '+' : ''}${stockMoney(v)}</td>`;
}

function stockPctCell(pct) {
  const v = Number(pct || 0);
  return `<td class="${v >= 0 ? 'stock-up' : 'stock-down'}">${v >= 0 ? '▲' : '▼'}${Math.abs(v).toFixed(1)}%</td>`;
}

function renderStock(data) {
  const r = data.rules || {};
  const p = data.portfolio || {};
  const companies = data.companies || [];
  const holdings = p.holdings || [];

  stockStatusEl.textContent =
    `${data.status_line}｜在市 ${companies.length} 家｜上涨 ${data.up} · 下跌 ${data.down}`;
  stockRulesEl.textContent =
    `开市 ${data.open_hour}:00~${data.close_hour}:00｜1 鱼干 = ${r.fish_to_catnip} 猫薄荷｜`
    + `${r.catnip_to_fish} 猫薄荷 = 1 鱼干｜手续费 ${Math.round((r.buy_fee || 0) * 100)}%｜`
    + `买入当天不能卖，次日开市后可卖`;
  stockExchangeEl.textContent =
    `充值 1 鱼干 → ${r.fish_to_catnip} 猫薄荷，提现 ${r.catnip_to_fish} 猫薄荷 → 1 鱼干；`
    + `当前猫薄荷约可提现 ${stockMoney(p.catnip_to_fish_est)} 鱼干`;

  stockWalletEl.innerHTML = [
    ['猫薄荷', stockMoney(p.catnip)],
    ['鱼干', stockMoney(p.fish)],
    ['持仓市值', stockMoney(Math.round(p.total_value || 0))],
    ['总浮动', `${Number(p.total_pnl || 0) >= 0 ? '+' : ''}${stockMoney(p.total_pnl)}`],
  ].map(([label, val]) => `
    <div class="stat"><div class="stat-num">${esc(val)}</div><div class="stat-label">${label}</div></div>`).join('');

  stockCodesEl.innerHTML = companies.map(
    (c) => `<option value="${esc(c.code)}">${esc(c.name)}</option>`).join('');

  stockMarketBodyEl.innerHTML = companies.map((c) => `
    <tr>
      <td>${esc(c.code)}</td>
      <td>${esc(c.name)}${c.policy ? `<div class="stock-policy">方针：${esc(c.policy)}</div>` : ''}</td>
      <td>${esc(c.country_name)}</td>
      <td>${esc(c.sector)}</td>
      <td>${Number(c.price).toFixed(1)}</td>
      ${stockPctCell(c.pct)}
    </tr>`).join('');
  if (!companies.length) {
    stockMarketBodyEl.innerHTML = '<tr><td colspan="6" class="room-empty">暂无行情喵</td></tr>';
  }
  stockMarketSubEl.textContent = `${data.status_line}｜行情每个整点更新`;

  stockHoldSubEl.textContent =
    `总市值 ${stockMoney(Math.round(p.total_value || 0))}｜总浮动 ${stockMoney(p.total_pnl)}`;

  if (!holdings.length) {
    stockHoldingsEl.innerHTML = '<p class="room-empty">当前空仓喵，先去大盘挑一只吧</p>';
  } else {
    const rows = holdings.map((h) => `
      <tr>
        <td>${esc(h.code)}</td>
        <td>${esc(h.name)}</td>
        <td>${h.shares}</td>
        <td>${h.sellable}</td>
        <td>${h.locked}</td>
        <td>${Number(h.avg_cost).toFixed(1)}</td>
        <td>${h.price ? Number(h.price).toFixed(1) : '—'}</td>
        <td>${stockMoney(Math.round(h.value))}</td>
        ${stockPnlCell(h.pnl)}
      </tr>`).join('');
    stockHoldingsEl.innerHTML = `
      <div class="stock-table-wrap">
        <table class="stock-table">
          <thead>
            <tr>
              <th>代码</th><th>名称</th><th>持有</th><th>可卖</th><th>锁定</th>
              <th>成本</th><th>现价</th><th>市值</th><th>浮动</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  const ranking = data.ranking || [];
  stockRankSubEl.textContent = `共 ${ranking.length} 位股东｜按累计盈亏排序`;
  const rankRow = (r, i) => `
    <div class="rank-row">
      <span class="rank-no">${i}</span>
      <span class="rank-name">${esc(r.nick)}</span>
      <span class="rank-val ${r.profit >= 0 ? 'stock-up' : 'stock-down'}">
        ${r.profit >= 0 ? '+' : ''}${stockMoney(r.profit)}（${r.pct >= 0 ? '+' : ''}${Number(r.pct).toFixed(1)}%）
      </span>
      <span class="rank-reward">资产 ${stockMoney(r.assets)}</span>
    </div>`;
  const bestRank = ranking.slice(0, 5);
  const worstRank = ranking.filter((r) => r.profit < 0).slice(-5).reverse();
  stockRankBestEl.innerHTML = bestRank.length
    ? bestRank.map((r, i) => rankRow(r, i + 1)).join('')
    : '<p class="room-empty">还没有人入场喵</p>';
  stockRankWorstEl.innerHTML = worstRank.length
    ? worstRank.map((r, i) => rankRow(r, i + 1)).join('')
    : '<p class="room-empty">暂时全员盈利，没人亏钱喵</p>';

  stockNewsEl.innerHTML = (data.news || []).length
    ? data.news.map((n) => `
      <div class="stock-news-item">
        <div class="stock-news-title">${esc(n.time)} ${esc(n.title)}</div>
        ${n.detail ? `<div class="stock-news-detail">${esc(n.detail)}</div>` : ''}
      </div>`).join('')
    : '<p class="room-empty">还没有新闻喵～ 开市后每个整点更新世界快报</p>';
}

async function loadStock() {
  const { status, data } = await api('/api/stock/overview');
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    stockMsgEl.textContent = data.msg || '加载失败喵';
    return;
  }
  stockMsgEl.textContent = '';
  stockMsgEl.classList.remove('ok');
  renderStock(data);
}

async function stockAction(path, body, actionName) {
  stockMsgEl.textContent = '';
  stockMsgEl.classList.remove('ok');
  const { status, data } = await api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (status === 401) { homePanel.classList.add('hidden'); showLogin(); return; }
  if (status !== 200 || !data.ok) {
    stockMsgEl.textContent = data.msg || `${actionName}失败喵`;
    return;
  }
  const msg = data.msg || `${actionName}完成喵`;
  stockMsgEl.textContent = msg;
  stockMsgEl.classList.toggle('ok', /成交|成功/.test(msg));
  if (data.overview) renderStock(data.overview);
  await refresh();  // 兑换会改动鱼干，同步顶部余额
}

document.getElementById('btn-stock-refresh').addEventListener('click', () => loadStock());

document.getElementById('btn-stock-buy').addEventListener('click', () => {
  const code = stockCodeEl.value.trim();
  const shares = stockSharesEl.value.trim();
  if (!code || !shares) {
    stockMsgEl.textContent = '股票和股数都要填喵';
    stockMsgEl.classList.remove('ok');
    return;
  }
  stockAction('/api/stock/buy', { code, shares }, '买入');
});

document.getElementById('btn-stock-sell').addEventListener('click', () => {
  const code = stockCodeEl.value.trim();
  const shares = stockSharesEl.value.trim();
  if (!code || !shares) {
    stockMsgEl.textContent = '股票和股数都要填喵';
    stockMsgEl.classList.remove('ok');
    return;
  }
  stockAction('/api/stock/sell', { code, shares }, '卖出');
});

document.getElementById('btn-stock-deposit').addEventListener('click', () => {
  const fish = stockFishEl.value.trim();
  if (!fish) {
    stockMsgEl.textContent = '先填要兑换的鱼干数量喵';
    stockMsgEl.classList.remove('ok');
    return;
  }
  stockAction('/api/stock/deposit', { fish }, '充值');
});

document.getElementById('btn-stock-withdraw').addEventListener('click', () => {
  const fish = stockFishEl.value.trim();
  if (!fish) {
    stockMsgEl.textContent = '先填要兑换的鱼干数量喵';
    stockMsgEl.classList.remove('ok');
    return;
  }
  stockAction('/api/stock/withdraw', { fish }, '提现');
});
