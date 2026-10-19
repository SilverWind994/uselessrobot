const loginPanel = document.getElementById('login-panel');
const homePanel = document.getElementById('home-panel');
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
  loginPanel.classList.remove('hidden');
  homePanel.classList.add('hidden');
  if (notice) setMsg(notice, false);
}

function showHome(player) {
  loginPanel.classList.add('hidden');
  homePanel.classList.remove('hidden');
  document.getElementById('player-name').textContent = player.nick || `玩家${player.qq}`;
  document.getElementById('player-qq').textContent = `QQ ${player.qq}`;
  document.getElementById('stat-fish').textContent = player.fish;
  document.getElementById('stat-stone').textContent = player.eye_stones;
  document.getElementById('stat-cats').textContent = player.cats;
  document.getElementById('stat-summon').textContent = player.summon_count;
  document.getElementById('stat-signin').textContent = player.signin_total;
}

async function refresh() {
  const { status, data } = await api('/api/me');
  if (status === 200 && data.ok) showHome(data.player);
  else showLogin();
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
    showHome(data.player);
  } else {
    setMsg(data.msg || '登录失败喵', false);
  }
});

document.getElementById('btn-logout').addEventListener('click', async () => {
  await api('/api/logout', { method: 'POST' });
  document.getElementById('input-pwd').value = '';
  showLogin('已登出喵');
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
  fkPanel.classList.remove('hidden');
  fkLobby.classList.remove('hidden');
  fkRoom.classList.add('hidden');
  fkCode = null;
  fkLobbyMsg.textContent = '';
  const { status, data } = await api('/api/farkle/mine');
  if (status === 401) { fkPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 200 && data.ok && data.code) { enterRoom(data.code); return; }
  await refreshRooms();
  clearInterval(fkRoomTimer);
  fkLobbyTimer = setInterval(refreshRooms, 2500);
}

function backToLobby() {
  clearInterval(fkRoomTimer);
  fkRoomTimer = null;
  fkCode = null;
  fkRoom.classList.add('hidden');
  fkLobby.classList.remove('hidden');
  refreshRooms();
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
    const meta = document.createElement('div');
    meta.className = 'room-meta';
    meta.innerHTML = `目标 ${r.target} 分 · `
      + (r.stones > 0 ? `<span class="room-stone">猫眼石 ${r.stones}</span>` : '普通局')
      + ` · 房间号 ${esc(r.code)}`;
    const host = document.createElement('div');
    host.className = 'room-host';
    host.textContent = r.host;
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary btn-sm';
    btn.textContent = '加入';
    btn.addEventListener('click', () => joinRoom(r.code));
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
  buildRoomDom();
  await pollRoom();
  clearInterval(fkRoomTimer);
  fkRoomTimer = setInterval(pollRoom, 1200);
}

async function pollRoom() {
  if (!fkCode) return;
  const { status, data } = await api('/api/farkle/state?code=' + encodeURIComponent(fkCode));
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
}

function buildRoomDom() {
  fkRoom.innerHTML = `
    <div class="card fk-head">
      <div class="fk-head-top">
        <div class="fk-title">Farkle · 目标 <span id="fk-target-show"></span> 分<span id="fk-stones-show"></span></div>
        <div class="fk-code">房间号 <b id="fk-code-show"></b></div>
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
      <div class="actions">
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
      <div class="actions">
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
    const v = document.getElementById('fk-bid-input').value.trim();
    if (v === '') { fkMsg('请先填写出价喵'); return; }
    fkAct('bid', { value: v });
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
  document.getElementById('fk-surrender').classList.toggle('hidden', isWaiting || isOver);
  if (isWaiting) {
    document.getElementById('fk-cancel').classList.toggle('hidden', state.my_index !== 0);
  }
  if (isAuction) renderAuction(state);
  if (isPlay) renderTable(state);
  if (isOver) renderResult(state);
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
    info.innerHTML = `由 <b>${esc(cur.name)}</b> 先出价`;
  } else {
    info.innerHTML = `当前出价 <b>${au.bid}</b>（由 <b>${esc(holder.name)}</b> 持有，`
      + `先手以 <b>${fmtOpen(au.bid)}</b> 分开局）`;
  }

  const mine = state.my_index >= 0 && state.my_index === curIdx;
  document.getElementById('fk-bid-input').disabled = !mine;
  document.getElementById('fk-bid').disabled = !mine;
  document.getElementById('fk-accept').disabled = !mine || au.bid == null;
  document.getElementById('fk-auction-hint').textContent = mine
    ? (au.bid == null ? '出价 50 的倍数，可为负数' : '加价要高于当前出价，或直接接受')
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
  const lockBtn = document.getElementById('fk-lock');
  const rollBtn = document.getElementById('fk-roll');
  const bankBtn = document.getElementById('fk-bank');
  lockBtn.classList.toggle('hidden', !isKeep);
  rollBtn.classList.toggle('hidden', !isDecide);
  bankBtn.classList.toggle('hidden', !isDecide);
  lockBtn.disabled = !myTurn || !fkSelected.size;
  rollBtn.disabled = !myTurn;
  bankBtn.disabled = !myTurn;
  document.getElementById('fk-table-hint').textContent = myTurn
    ? (isKeep ? '选中后点「锁定选中」' : '掷有爆骰风险，入账则收下本回合分')
    : '等待对方行动……';
}

function renderResult(state) {
  const winner = state.players.find((p) => p.qq === state.winner);
  const lines = [`🏆 ${winner ? winner.name : '?'} 获胜！`];
  state.players.forEach((p) => lines.push(`${p.name}：${p.total} 分`));
  (state.settle_lines || []).forEach((l) => lines.push(l));
  document.getElementById('fk-result').innerHTML =
    '<div class="panel-title">对局结束</div>'
    + lines.map((l) => `<div class="line">${esc(l)}</div>`).join('');
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
  clearInterval(fkLobbyTimer);
  clearInterval(fkRoomTimer);
  fkPanel.classList.add('hidden');
  homePanel.classList.remove('hidden');
  refresh();
});
document.getElementById('fk-stones-on').addEventListener('change', (e) => {
  document.getElementById('fk-stones').disabled = !e.target.checked;
});
document.getElementById('btn-fk-create').addEventListener('click', createRoom);
