const BASE    = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';
const CRITICAL_WEAR = 250; // mirrors WEAR_THRESHOLD_CRITICAL in backend

let machines = [];
const wsMap  = {};

// ─── WS auto-update debounce: avoid hammering /update_car_wear if many
// sensor messages arrive in quick succession
const wsPending = {}; // car_id → debounce timer

// ─── UTILS ───────────────────────────────────────────────────────────────────
function relTime(iso) {
  if (!iso) return '—';
  const s = Math.round((Date.now() - new Date(iso)) / 1000);
  if (s < 5)    return 'just now';
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}
function fmt(n) { return Number(n).toFixed(2); }
function wearPct(w) { return Math.min(100, Math.round((w / CRITICAL_WEAR) * 100)); }
function statusLabel(s) {
  return { NORMAL: 'Normal', WARNING: 'Warning', REPAIR_NEEDED: 'Repair needed', CRITICAL: 'Critical' }[s] ?? s;
}

function showToast(msg, type = 'ok', ms = 3500) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), ms);
}
function setSyncNow() {
  document.getElementById('last-sync').textContent = 'synced ' + new Date().toLocaleTimeString();
}
function setWsBadge(cls, text) {
  const el = document.getElementById('ws-badge');
  el.className = `badge ${cls}`;
  el.textContent = text;
}
function refreshWsBadge() {
  const n = Object.keys(wsMap).length;
  if (n === 0) setWsBadge('', 'ws off');
  else         setWsBadge('live', `ws ×${n} live`);
}

// ─── RENDER ───────────────────────────────────────────────────────────────────
function render() {
  const grid = document.getElementById('grid');
  if (!machines.length) {
    grid.innerHTML = `
      <div class="state-msg">
        <strong>No cars found</strong>
        No rows in <code>car_wear</code> table yet.<br>
        Send data via <code>POST /processed_agent_data/</code>, then click Оновити for a car.
      </div>`;
    return;
  }
  const order = { CRITICAL: 0, REPAIR_NEEDED: 1, WARNING: 2, NORMAL: 3 };
  const sorted = [...machines].sort((a, b) =>
    (order[a.wear_status] ?? 9) - (order[b.wear_status] ?? 9)
  );
  grid.innerHTML = sorted.map(cardHTML).join('');
}

function cardHTML(m) {
  const status = m.wear_status ?? 'NORMAL';
  const pct    = wearPct(m.total_wear);
  return `
  <div class="card ${status}" id="card-${m.car_id}">
    <div class="loading-overlay"><div class="spinner"></div></div>
    <div class="card-header">
      <div class="machine-id">car_id<strong>${m.car_id}</strong></div>
      <span class="status-pill">${statusLabel(status)}</span>
    </div>
    <div>
      <div class="wear-row">
        <span class="wear-value">${fmt(m.total_wear)}</span>
        <span class="wear-unit">wear units</span>
        <span class="delta-badge" id="delta-${m.car_id}"></span>
      </div>
      <div class="wear-bar-wrap">
        <div class="wear-bar" style="width:${pct}%"></div>
      </div>
      <div class="bar-labels">
        <span>0</span><span>${pct}% of critical</span><span>${CRITICAL_WEAR}</span>
      </div>
    </div>
    <div class="meta">
      <div class="row">Status <em>${statusLabel(status)}</em></div>
      <div class="row">Last update <em id="ts-${m.car_id}">${relTime(m.last_update_timestamp)}</em></div>
    </div>
    <div class="card-actions">
      <button class="btn-update" onclick="handleUpdate('${m.car_id}')">Оновити</button>
      <button class="btn-reset"  onclick="handleReset('${m.car_id}')">Скинути</button>
    </div>
  </div>`;
}

// ─── PATCH (no full re-render) ────────────────────────────────────────────────
function patchCard(m, delta) {
  const idx = machines.findIndex(x => x.car_id === m.car_id);
  if (idx === -1) { machines.push(m); render(); return; }
  machines[idx] = m;

  const card = document.getElementById(`card-${m.car_id}`);
  if (!card) { render(); return; }

  const status = m.wear_status ?? 'NORMAL';
  const pct    = wearPct(m.total_wear);

  card.className = `card ${status}`;
  card.querySelector('.status-pill').textContent = statusLabel(status);
  card.querySelector('.wear-value').textContent  = fmt(m.total_wear);
  card.querySelector('.wear-bar').style.width    = pct + '%';
  card.querySelectorAll('.bar-labels span')[1].textContent = `${pct}% of critical`;
  card.querySelectorAll('.meta .row em')[0].textContent    = statusLabel(status);

  const tsEl = document.getElementById(`ts-${m.car_id}`);
  if (tsEl) tsEl.textContent = relTime(m.last_update_timestamp);

  if (delta !== undefined && delta > 0) {
    const d = document.getElementById(`delta-${m.car_id}`);
    if (d) {
      d.textContent = `+${fmt(delta)}`;
      d.classList.add('show');
      setTimeout(() => d.classList.remove('show'), 3000);
    }
  }
  setSyncNow();
}

function setCardLoading(car_id, on) {
  const card = document.getElementById(`card-${car_id}`);
  if (!card) return;
  card.classList.toggle('loading', on);
  card.querySelectorAll('button').forEach(b => b.disabled = on);
}

function flashCard(car_id) {
  const card = document.getElementById(`card-${car_id}`);
  if (!card) return;
  card.classList.remove('ws-flash');
  void card.offsetWidth;
  card.classList.add('ws-flash');
  setTimeout(() => card.classList.remove('ws-flash'), 1400);
}

// ─── API ──────────────────────────────────────────────────────────────────────
async function fetchAllCars() {
  try {
    const r = await fetch(`${BASE}/car_wear/`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    machines = await r.json();
    render();
    setSyncNow();
    machines.forEach(m => ensureWS(m.car_id));
  } catch (e) {
    document.getElementById('grid').innerHTML = `
      <div class="state-msg">
        <strong>Cannot reach backend</strong>
        ${e.message}<br><br>
        Is FastAPI running at <code>${BASE}</code>?
      </div>`;
    setWsBadge('err', 'offline');
  }
}

async function handleUpdate(car_id, silent = false) {
  if (!silent) setCardLoading(car_id, true);
  try {
    const r = await fetch(`${BASE}/update_car_wear/${encodeURIComponent(car_id)}`, { method: 'POST' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail ?? r.statusText);
    }
    const data = await r.json(); 
    patchCard(data, data.added_this_time);
    if (!silent) {
      const msg = data.added_this_time > 0
        ? `${car_id}: +${fmt(data.added_this_time)} wear added`
        : `${car_id}: no new sensor data since last update`;
      showToast(msg, data.added_this_time > 0 ? 'ok' : 'info');
    }
  } catch (e) {
    if (!silent) showToast(`Update failed (${car_id}): ${e.message}`, 'err');
    else console.warn(`Auto-update failed for ${car_id}:`, e);
  } finally {
    if (!silent) setCardLoading(car_id, false);
  }
}

async function handleReset(car_id) {
  if (!confirm(`Reset wear to 0 for "${car_id}"?\nThis cannot be undone.`)) return;
  setCardLoading(car_id, true);
  try {
    const r = await fetch(`${BASE}/reset_car_wear/${encodeURIComponent(car_id)}`, { method: 'POST' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail ?? r.statusText);
    }
    const data = await r.json();
    patchCard(data, undefined);
    showToast(`${car_id}: reset to 0`, 'ok');
  } catch (e) {
    showToast(`Reset failed (${car_id}): ${e.message}`, 'err');
  } finally {
    setCardLoading(car_id, false);
  }
}

// ─── WEBSOCKET ────────────────────────────────────────────────────────────────
function ensureWS(car_id) {
  if (wsMap[car_id]) return;

  let ws;
  try { ws = new WebSocket(`${WS_BASE}/ws/${encodeURIComponent(car_id)}`); }
  catch (e) { console.warn(`WS open failed for ${car_id}:`, e); return; }

  wsMap[car_id] = ws;

  ws.onopen = () => { refreshWsBadge(); };

  ws.onmessage = evt => {
    flashCard(car_id);

    try {
      const msg = JSON.parse(evt.data);
      if (msg.road_state) {
        showToast(
          `${car_id} → ${msg.road_state}  dmg: ${fmt(msg.damage_coefficient ?? 0)}`,
          'info', 2500
        );
      }
    } catch {}

    clearTimeout(wsPending[car_id]);
    wsPending[car_id] = setTimeout(() => {
      handleUpdate(car_id, true);
    }, 800);
  };

  ws.onclose = () => {
    delete wsMap[car_id];
    refreshWsBadge();
    setTimeout(() => ensureWS(car_id), 5000);
  };

  ws.onerror = () => ws.close();
}

setInterval(() => {
  machines.forEach(m => {
    const el = document.getElementById(`ts-${m.car_id}`);
    if (el) el.textContent = relTime(m.last_update_timestamp);
  });
}, 30_000);

fetchAllCars();