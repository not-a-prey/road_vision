const BASE          = 'http://localhost:8000';
const WS_BASE       = 'ws://localhost:8000';
const CRITICAL_WEAR = 250;
const TRAIL_MAX     = 50; 

let machines = [];
const wsMap  = {};
const wsPending = {};

// ─── MAP STATE ───
const carColors  = {};
const carMarkers = {};
const carTrails  = {};
const carPoints  = {};
const carHidden  = {};

let map;
let mapHasData = false;
let selectedCar = null;

const COLOR_PALETTE = [
  '#2563eb','#dc2626','#16a34a','#d97706','#7c3aed',
  '#0891b2','#be185d','#15803d','#b45309','#6d28d9',
  '#0e7490','#9f1239','#065f46','#92400e','#4338ca','#0f766e',
];
let colorIdx = 0;

function carColor(car_id) {
  if (!carColors[car_id]) {
    carColors[car_id] = COLOR_PALETTE[colorIdx % COLOR_PALETTE.length];
    colorIdx++;
  }
  return carColors[car_id];
}

// ─── UTILS ───
function relTime(iso) {
  if (!iso) return '—';
  let dateStr = iso;
  if (!dateStr.endsWith('Z') && !dateStr.includes('+')) dateStr += 'Z';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return 'format err';

  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 5)    return 'just now';
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  const hours = Math.floor(s / 3600);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
}

function fmt(n) { return Number(n).toFixed(2); }
function fmtGps(n) { return n ? Number(n).toFixed(5) : '—'; }
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

// ─── MAP INIT & LOGIC ───
function initMap() {
  map = L.map('map', { zoomControl: true }).setView([50.45, 30.52], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19,
  }).addTo(map);
}

function makeMarkerIcon(color, isSelected) {
  const size  = isSelected ? 16 : 12;
  const ring  = isSelected ? 4  : 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size+ring*2}" height="${size+ring*2}">
    <circle cx="${size/2+ring}" cy="${size/2+ring}" r="${size/2+ring}" fill="${color}" opacity="0.25"/>
    <circle cx="${size/2+ring}" cy="${size/2+ring}" r="${size/2}" fill="${color}" stroke="white" stroke-width="1.5"/>
  </svg>`;
  const total = size + ring * 2;
  return L.divIcon({ html: svg, className: '', iconSize: [total, total], iconAnchor: [total/2, total/2] });
}

function updateMapForCar(car_id, lat, lng, roadState, dmg) {
  if (!map || !lat || !lng) return;

  const color = carColor(car_id);
  const hidden = !!carHidden[car_id];
  const latLng = [lat, lng];

  if (!carPoints[car_id]) carPoints[car_id] = [];
  carPoints[car_id].push(latLng);
  if (carPoints[car_id].length > TRAIL_MAX) carPoints[car_id].shift();

  if (!carTrails[car_id]) {
    carTrails[car_id] = L.polyline(carPoints[car_id], { color, weight: 2.5, opacity: 0.55 }).addTo(map);
  } else {
    carTrails[car_id].setLatLngs(carPoints[car_id]);
  }
  if (hidden) carTrails[car_id].setStyle({ opacity: 0 });

  const isSelected = selectedCar === car_id;
  const icon = makeMarkerIcon(color, isSelected);
  if (!carMarkers[car_id]) {
    const marker = L.marker(latLng, { icon }).addTo(map);
    marker.bindPopup('', { maxWidth: 220, minWidth: 160 });
    marker.on('click', () => selectCar(car_id));
    carMarkers[car_id] = marker;
  } else {
    carMarkers[car_id].setLatLng(latLng);
    carMarkers[car_id].setIcon(icon);
  }

  const m = machines.find(x => x.car_id === car_id);
  carMarkers[car_id].setPopupContent(`
    <div class="map-popup">
      <div class="map-popup-id" style="color:${color}">${car_id}</div>
      <div class="map-popup-row">Road state <em>${roadState ?? '—'}</em></div>
      <div class="map-popup-row">Damage <em>${fmt(dmg ?? 0)}</em></div>
      ${m ? `<div class="map-popup-row">Wear <em>${fmt(m.total_wear)}</em></div>` : ''}
      <div class="map-popup-row">Lat <em>${fmtGps(lat)}</em></div>
      <div class="map-popup-row">Lng <em>${fmtGps(lng)}</em></div>
    </div>`);

  if (hidden) carMarkers[car_id].setOpacity(0);

  if (!mapHasData) {
    mapHasData = true;
    document.getElementById('map-no-data').classList.add('hidden');
    document.getElementById('map-legend').style.display = '';
  }

  if (carPoints[car_id].length === 1) {
    const all = Object.values(carPoints).flat();
    if (all.length) map.fitBounds(L.latLngBounds(all), { padding: [40, 40], maxZoom: 14 });
  } else if (isSelected) {
    map.panTo(latLng, { animate: true, duration: 0.4 });
  }

  const gpsEl = document.getElementById(`gps-${car_id}`);
  if (gpsEl) gpsEl.innerHTML = `<span>LAT: ${fmtGps(lat)}</span> <span>LNG: ${fmtGps(lng)}</span>`;

  updateLegend();
}

function updateLegend() {
  const container = document.getElementById('legend-items');
  const ids = Object.keys(carColors);
  if (!ids.length) return;
  container.innerHTML = ids.map(id => `
    <div class="legend-item ${carHidden[id] ? 'hidden-car' : ''}" onclick="toggleCarVisibility('${id}')">
      <span class="legend-dot" style="background:${carColors[id]}"></span>
      <span class="legend-label">${id}</span>
    </div>`).join('');
}

function toggleCarVisibility(car_id) {
  carHidden[car_id] = !carHidden[car_id];
  const hidden = carHidden[car_id];
  if (carMarkers[car_id]) carMarkers[car_id].setOpacity(hidden ? 0 : 1);
  if (carTrails[car_id])  carTrails[car_id].setStyle({ opacity: hidden ? 0 : 0.55 });
  updateLegend();
}

function selectCar(car_id) {
  const prev = selectedCar;
  selectedCar = car_id;

  if (prev && carMarkers[prev]) carMarkers[prev].setIcon(makeMarkerIcon(carColor(prev), false));
  if (carMarkers[car_id]) {
    carMarkers[car_id].setIcon(makeMarkerIcon(carColor(car_id), true));
    carMarkers[car_id].openPopup();
    if (carPoints[car_id]?.length) map.panTo(carMarkers[car_id].getLatLng(), { animate: true, duration: 0.4 });
  }

  document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
  const card = document.getElementById(`card-${car_id}`);
  if (card) { card.classList.add('active'); card.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
}

// ─── ACCELEROMETER LOGIC ───
const MAX_G = 20.0;
function updateAccelerometer(car_id, x, y, z) {
  const waitEl = document.getElementById(`accel-wait-${car_id}`);
  const axesEl = document.getElementById(`accel-axes-${car_id}`);
  const dotEl  = document.getElementById(`accel-dot-${car_id}`);
  if (!axesEl) return;
  if (waitEl) waitEl.style.display = 'none';
  axesEl.style.display = 'flex';
  if (dotEl) {
    dotEl.classList.add('active');
    clearTimeout(dotEl._t);
    dotEl._t = setTimeout(() => dotEl.classList.remove('active'), 600);
  }
  [['x',x],['y',y],['z',z]].forEach(([axis, val]) => {
    const valEl = document.getElementById(`accel-val-${axis}-${car_id}`);
    const barEl = document.getElementById(`accel-bar-${axis}-${car_id}`);
    if (!valEl || !barEl) return;
    valEl.textContent = (val >= 0 ? '+' : '') + Number(val).toFixed(3);
    const clamped = Math.max(-MAX_G, Math.min(MAX_G, val));
    const half    = Math.abs(clamped / MAX_G) * 50;
    if (clamped >= 0) { barEl.style.left = '50%';           barEl.style.width = half + '%'; }
    else              { barEl.style.left = (50-half) + '%'; barEl.style.width = half + '%'; }
  });
}

// ─── RENDER ───
function render() {
  const grid = document.getElementById('cards-pane');
  if (!machines.length) {
    grid.innerHTML = `
      <div class="state-msg">
        <strong>No cars found</strong>
        No rows in <code>car_wear</code> table yet.
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
  const color  = carColor(m.car_id);

  return `
  <div class="card ${status}" id="card-${m.car_id}" onclick="selectCar('${m.car_id}')" style="--accent:${color}">
    <div class="loading-overlay"><div class="spinner"></div></div>
    
    <div class="card-header">
      <div class="machine-id">car_id<strong style="color:${color}">${m.car_id}</strong></div>
      <span class="status-pill">${statusLabel(status)}</span>
    </div>
    
    <div>
      <div class="wear-row">
        <span class="wear-value">${fmt(m.total_wear)}</span>
        <span class="wear-unit">wear units</span>
        <span class="delta-badge" id="delta-${m.car_id}"></span>
      </div>
      <div class="wear-bar-wrap">
        <div class="wear-bar" style="width:${pct}%;background:${color}"></div>
      </div>
      <div class="bar-labels">
        <span>0</span><span>${pct}% of ${CRITICAL_WEAR}</span><span>${CRITICAL_WEAR}</span>
      </div>
    </div>
    
    <div class="meta">
      <div class="row">Status <em>${statusLabel(status)}</em></div>
      <div class="row">Updated <em id="ts-${m.car_id}">${relTime(m.last_update_timestamp)}</em></div>
      <div class="gps-row" id="gps-${m.car_id}">no GPS data yet</div>
    </div>

    <div class="accel-section">
      <div class="accel-label">
        Accelerometer
        <span class="accel-live-dot" id="accel-dot-${m.car_id}"></span>
      </div>
      <div class="accel-waiting" id="accel-wait-${m.car_id}">waiting for WS data…</div>
      <div class="accel-axes" id="accel-axes-${m.car_id}" style="display:none">
        ${['x','y','z'].map(ax => `
        <div class="accel-axis">
          <span class="accel-axis-name ${ax}">${ax.toUpperCase()}</span>
          <div class="accel-bar-track">
            <div class="accel-bar-fill" id="accel-bar-${ax}-${m.car_id}" style="left:50%;width:0%"></div>
          </div>
          <span class="accel-val" id="accel-val-${ax}-${m.car_id}">—</span>
        </div>`).join('')}
      </div>
    </div>

    <div class="card-actions">
      <button class="btn-update" onclick="event.stopPropagation();handleUpdate('${m.car_id}')">Оновити</button>
      <button class="btn-reset"  onclick="event.stopPropagation();handleReset('${m.car_id}')">Скинути</button>
    </div>
  </div>`;
}

function patchCard(m, delta) {
  const idx = machines.findIndex(x => x.car_id === m.car_id);
  if (idx === -1) { machines.push(m); render(); return; }
  machines[idx] = m;

  const card = document.getElementById(`card-${m.car_id}`);
  if (!card) { render(); return; }

  const status = m.wear_status ?? 'NORMAL';
  const pct    = wearPct(m.total_wear);
  const color  = carColor(m.car_id);

  ['NORMAL','WARNING','REPAIR_NEEDED','CRITICAL'].forEach(s => card.classList.remove(s));
  card.classList.add(status);

  card.querySelector('.status-pill').textContent = statusLabel(status);
  card.querySelector('.wear-value').textContent  = fmt(m.total_wear);
  card.querySelector('.wear-bar').style.width    = pct + '%';
  card.querySelector('.wear-bar').style.background = color;
  card.querySelectorAll('.bar-labels span')[1].textContent = `${pct}% of ${CRITICAL_WEAR}`;
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

// ─── API ───
async function fetchAllCars() {
  try {
    const r = await fetch(`${BASE}/car_wear/`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    machines = await r.json();
    render();
    setSyncNow();
    machines.forEach(m => ensureWS(m.car_id));
  } catch (e) {
    document.getElementById('cards-pane').innerHTML = `
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

// ─── WEBSOCKET ───
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
      
      // Accelerometer
      if (msg.x !== undefined && msg.y !== undefined && msg.z !== undefined) {
        const scale = 16384.0;
        const gX = msg.x / scale;
        const gY = msg.y / scale;
        const gZ = msg.z / scale;
        
        updateAccelerometer(car_id, gX, gY, gZ);
      }

      // Map GPS
      if (msg.latitude !== undefined && msg.longitude !== undefined) {
        updateMapForCar(car_id, msg.latitude, msg.longitude, msg.road_state, msg.damage_coefficient);
      }

      if (msg.road_state) {
        showToast(
          `${car_id} → ${msg.road_state}  dmg: ${fmt(msg.damage_coefficient ?? 0)}`,
          'info', 2500
        );
      }
    } catch (e) {
      console.error("WS Parse Error:", e);
    }

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

// Initialize Map & Fetch Data
initMap();
fetchAllCars();