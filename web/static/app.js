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
