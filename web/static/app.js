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
  if (notice) setMsg(notice, false);
}

function showPwd(forced) {
  loginPanel.classList.add('hidden');
  homePanel.classList.add('hidden');
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
  pwdPanel.classList.add('hidden');
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
    const ongoing = r.phase !== 'waiting';
    const meta = document.createElement('div');
    meta.className = 'room-meta';
    meta.innerHTML = (ongoing ? '<span class="room-stone">对局中</span> · ' : '')
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
  document.getElementById('fk-bid-input').disabled = !mine;
  document.getElementById('fk-bid').disabled = !mine;
  document.getElementById('fk-accept').disabled = !mine || au.bid == null;
  document.getElementById('fk-auction-hint').textContent = mine
    ? (au.bid == null
        ? '正数 = 拿先手但以该负分开局；负数 = 拿先手反而以正分开局'
        : '出价需高于当前最高出价；或点「接受」让出先手')
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
  yzRoom.classList.add('hidden');
  yzLobby.classList.remove('hidden');
  refreshYzRooms();
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
  buildYzRoomDom();
  await pollYzRoom();
  clearInterval(yzRoomTimer);
  yzRoomTimer = setInterval(pollYzRoom, 1200);
}

async function pollYzRoom() {
  if (!yzCode) return;
  const { status, data } = await api('/api/yahtzee/state?code=' + encodeURIComponent(yzCode));
  if (status === 401) { clearInterval(yzRoomTimer); yzPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 404) { yzMsg('房间已结束喵'); backToYzLobby(); return; }
  if (status !== 200 || !data.ok) return;
  const s = yzSignature(data.room);
  if (s !== yzSig) {
    yzSig = s;
    renderYzRoom(data.room);
  }
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
  document.getElementById('yz-result').innerHTML =
    '<div class="panel-title">对局结束</div>'
    + lines.map((l) => `<div class="line">${esc(l)}</div>`).join('');
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
  clearInterval(yzLobbyTimer);
  clearInterval(yzRoomTimer);
  yzPanel.classList.add('hidden');
  homePanel.classList.remove('hidden');
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
  if (!mjCode) return;
  const body = Object.assign({ code: mjCode, action: action }, extra || {});
  const { status, data } = await api('/api/mahjong17/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (status === 200 && data.ok) {
    mjSig = mjSignature(data.room);
    renderMjRoom(data.room);
  } else {
    mjMsg(data.msg || '操作失败喵');
  }
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
  buildMjRoomDom();
  await pollMjRoom();
  clearInterval(mjRoomTimer);
  mjRoomTimer = setInterval(pollMjRoom, 1200);
}

async function pollMjRoom() {
  if (!mjCode) return;
  const { status, data } = await api('/api/mahjong17/state?code=' + encodeURIComponent(mjCode));
  if (status === 401) { clearInterval(mjRoomTimer); mjPanel.classList.add('hidden'); showLogin(); return; }
  if (status === 404) { mjMsg('房间已结束喵'); backToMjLobby(); return; }
  if (status !== 200 || !data.ok) return;
  const s = mjSignature(data.room);
  if (s !== mjSig) {
    mjSig = s;
    renderMjRoom(data.room);
  }
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
  fkToggle('mj-waiting', isWaiting);
  fkToggle('mj-select', isSelect);
  fkToggle('mj-play', isPlay);
  fkToggle('mj-result', isOver);

  const spectator = !state.is_player;
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

  if (isSelect) renderMjSelect(state);
  if (isPlay) renderMjPlay(state);
  if (isOver) renderMjResult(state);
  renderMjLog(state);
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
  document.getElementById('mj-result').innerHTML = html.join('');
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
  clearInterval(mjLobbyTimer);
  clearInterval(mjRoomTimer);
  mjPanel.classList.add('hidden');
  homePanel.classList.remove('hidden');
  refresh();
});
document.getElementById('btn-mj-create').addEventListener('click', createMjRoom);
