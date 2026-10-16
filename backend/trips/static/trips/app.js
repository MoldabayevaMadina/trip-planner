const $ = (id) => document.getElementById(id);
const esc = (t) => { const d = document.createElement('div'); d.textContent = t ?? ''; return d.innerHTML; };
const CAT = { sight:'🏛', museum:'🖼', food:'🍽', walk:'🚶', shopping:'🛍', other:'📍' };
let state = { trips: [], tripId: null, data: null, dayId: null, picked: null };
let map;

async function api(path, opts = {}) {
  const r = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = data.detail || Object.entries(data).map(([k, v]) => `${k}: ${[].concat(v).join(' ')}`).join('; ');
    throw new Error(msg || r.statusText);
  }
  return data;
}

const fmtDate = (s, opts = { day: 'numeric', month: 'short' }) => new Date(s + 'T00:00').toLocaleDateString('en-GB', opts);

async function loadTrips() {
  state.trips = await api('/trips/');
  $('trips').innerHTML = state.trips.map(t => `
    <div class="trip ${t.id === state.tripId ? 'active' : ''}" onclick="openTrip(${t.id})">
      <b>${esc(t.title)}</b>
      <small>${esc(t.city)}${t.country ? ', ' + esc(t.country) : ''} · ${fmtDate(t.start_date)} – ${fmtDate(t.end_date)} · ${t.places_count} places</small>
    </div>`).join('') || '<p class="muted">No trips yet.</p>';
}

async function openTrip(id, keepDay = false) {
  state.tripId = id;
  if (!keepDay) state.dayId = null;
  loadTrips();
  try {
    state.data = await api(`/trips/${id}/days/`);
  } catch (e) { if (map) { map.remove(); map = null; } $('main').innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  const days = state.data.days;
  if (!state.dayId || !days.find(d => d.id === state.dayId)) state.dayId = days[0]?.id;
  render();
}

function render() {
  if (map) { map.remove(); map = null; }   // remove the old map before its container is replaced
  const { trip, days, weather_available } = state.data;
  const day = days.find(d => d.id === state.dayId);
  const daysLeft = Math.ceil((new Date(trip.start_date + 'T00:00') - new Date()) / 86400000);

  $('main').innerHTML = `
    <div class="head">
      <div>
        <h3>${esc(trip.title)}</h3>
        <p>${esc(trip.city)}${trip.country ? ', ' + esc(trip.country) : ''} · ${fmtDate(trip.start_date)} – ${fmtDate(trip.end_date)}
           ${daysLeft > 0 ? ` · starts in ${daysLeft} day${daysLeft === 1 ? '' : 's'}` : ''}</p>
      </div>
      <button class="ghost" onclick="deleteTrip()">Delete trip</button>
    </div>
    <div class="days">${days.map(d => `
      <div class="day ${d.id === state.dayId ? 'active' : ''}" onclick="selectDay(${d.id})">
        <div class="d">${fmtDate(d.date, { weekday: 'short', day: 'numeric', month: 'short' })}</div>
        <div class="w">${d.weather ? d.weather.icon : '·'}</div>
        <small>${d.weather && d.weather.temp_max !== null ? `${Math.round(d.weather.temp_max)}° / ${Math.round(d.weather.temp_min)}°` : 'no data'}</small>
      </div>`).join('')}
    </div>
    ${!weather_available ? '<div class="hint">Weather service is unavailable right now. The plan works, weather will appear later.</div>' : ''}
    ${day && day.weather && day.weather.rainy ? `<div class="hint">${day.weather.icon} ${esc(day.weather.text)} expected on this day. Maybe plan museums and indoor places.</div>` : ''}
    ${day && day.weather && day.weather.source === 'last_year' ? `<div class="muted">Too far for a forecast: showing the weather on the same dates last year. The real forecast appears ~2 weeks before the trip.</div>` : ''}
    <div id="map"></div>
    <div class="places">
      ${day && day.note ? `<p class="muted">📝 ${esc(day.note)}</p>` : ''}
      ${day && day.places.length ? day.places.map((p, i) => `
        <div class="place ${p.visited ? 'visited' : ''}">
          <div class="num">${i + 1}</div>
          <div class="info"><b>${CAT[p.category] || '📍'} ${esc(p.name)}</b>
            <span class="muted">${p.time ? p.time.slice(0, 5) + ' · ' : ''}${esc(p.address || p.category)}</span></div>
          <input type="checkbox" title="Visited" ${p.visited ? 'checked' : ''} onchange="toggleVisited(${p.id}, this.checked)">
          <button class="ghost" title="Remove" onclick="deletePlace(${p.id})">✕</button>
        </div>`).join('') : '<p class="muted">No places on this day yet. Add the first one below.</p>'}
    </div>
    <form class="add" id="place-form">
      <div><label>Place</label><input name="name" placeholder="Galata Tower" required></div>
      <div><label>Time</label><input name="time" type="time"></div>
      <div><label>Type</label><select name="category">
        ${Object.entries(CAT).map(([k, v]) => `<option value="${k}">${v} ${k}</option>`).join('')}</select></div>
      <div><button>Add</button></div>
    </form>
    <div class="muted" id="pick-hint">${state.picked
      ? `📍 Point picked on the map (${state.picked.lat.toFixed(5)}, ${state.picked.lng.toFixed(5)}). Enter a name and press Add. <a href="#" onclick="clearPick(); return false;">Cancel</a>`
      : 'Tip: click on the map to choose the exact point, or just type a name to search for it.'}</div>
    <div class="err" id="place-err"></div>`;

  $('place-form').addEventListener('submit', addPlace);
  drawMap(trip, day);
}

function drawMap(trip, day) {
  map = L.map('map', { zoomAnimation: false, fadeAnimation: false }).setView([trip.latitude, trip.longitude], 12);
   L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
    referrerPolicy: 'strict-origin-when-cross-origin'
  }).addTo(map);
  const places = day ? day.places : [];
  const points = places.map(p => [p.latitude, p.longitude]);
  places.forEach((p, i) => {
    const icon = L.divIcon({ className: '', html: `<div class="pin ${p.visited ? 'done' : ''}"><span>${i + 1}</span></div>`, iconSize: [28, 28], iconAnchor: [14, 28] });
    L.marker([p.latitude, p.longitude], { icon }).addTo(map)
      .bindPopup(`<b>${esc(p.name)}</b><br>${p.time ? p.time.slice(0, 5) : ''} ${CAT[p.category] || ''}`);
  });
  if (points.length > 1) L.polyline(points, { color: '#0f766e', weight: 4, opacity: .7, dashArray: '8 8' }).addTo(map);
  if (points.length) map.fitBounds(points, { padding: [40, 40], maxZoom: 15, animate: false });


  if (state.picked) {
    L.circleMarker([state.picked.lat, state.picked.lng], { radius: 9, color: '#b45309', weight: 3, fillOpacity: .3 }).addTo(map);
  }


  map.on('click', (e) => {
    state.picked = { lat: e.latlng.lat, lng: e.latlng.lng };
    render();
    document.querySelector('#place-form input[name=name]').focus();
  });
}

function selectDay(id) { state.dayId = id; state.picked = null; render(); }

async function addPlace(e) {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  if (!body.time) delete body.time;
  if (state.picked) {
    body.latitude = Number(state.picked.lat.toFixed(6));
    body.longitude = Number(state.picked.lng.toFixed(6));
  }
  $('place-err').textContent = state.picked ? 'Saving…' : 'Searching on the map…';
  try {
    await api(`/days/${state.dayId}/places/`, { method: 'POST', body: JSON.stringify(body) });
    state.picked = null;
    await openTrip(state.tripId, true);
  } catch (err) { $('place-err').textContent = err.message; }
}

function clearPick() { state.picked = null; render(); }

async function toggleVisited(id, visited) {
  await api(`/places/${id}/`, { method: 'PATCH', body: JSON.stringify({ visited }) });
  openTrip(state.tripId, true);
}

async function deletePlace(id) {
  await api(`/places/${id}/`, { method: 'DELETE' });
  openTrip(state.tripId, true);
}

async function deleteTrip() {
  if (!confirm('Delete this trip with all its places?')) return;
  await api(`/trips/${state.tripId}/`, { method: 'DELETE' });
  state.tripId = null; state.data = null;
  if (map) { map.remove(); map = null; }
  $('main').innerHTML = '<div class="empty">Choose a trip or create a new one.</div>';
  loadTrips();
}

$('trip-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('trip-err').textContent = 'Finding the city…';
  try {
    const trip = await api('/trips/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
    e.target.reset(); $('trip-err').textContent = '';
    openTrip(trip.id);
  } catch (err) { $('trip-err').textContent = err.message; }
});

loadTrips().then(() => { if (state.trips.length) openTrip(state.trips[0].id); });