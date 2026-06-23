// SwimChi - client-side filtering and rendering

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DAYS_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

let appData = null;  // {facilities, slots, swim_types}
let facilityMap = {};  // id → facility
let userLat = null;
let userLon = null;

// Cookie helpers
function getCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

function setCookie(name, value, days) {
  const d = new Date();
  d.setTime(d.getTime() + days * 86400000);
  document.cookie = name + '=' + encodeURIComponent(value) + ';expires=' + d.toUTCString() + ';path=/;SameSite=Lax';
}

function getFavorites() {
  const raw = getCookie('swimchi_favs');
  return raw ? JSON.parse(raw) : [];
}

function setFavorites(favs) {
  setCookie('swimchi_favs', JSON.stringify(favs), 365);
}

function toggleFavorite(facilityId) {
  let favs = getFavorites();
  if (favs.includes(facilityId)) {
    favs = favs.filter(id => id !== facilityId);
  } else {
    favs.push(facilityId);
  }
  setFavorites(favs);
  render();
}

// Save/load filter state
function saveFilters() {
  const state = {
    type: document.getElementById('filter-type').value,
    day: document.getElementById('filter-day').value,
    pool: document.getElementById('filter-pool').value,
    distance: document.getElementById('filter-distance').value,
    favorites: document.getElementById('filter-favorites').checked,
  };
  setCookie('swimchi_filters', JSON.stringify(state), 30);
}

function loadFilters() {
  const raw = getCookie('swimchi_filters');
  if (!raw) return;
  try {
    const state = JSON.parse(raw);
    if (state.type) document.getElementById('filter-type').value = state.type;
    if (state.day) document.getElementById('filter-day').value = state.day;
    if (state.pool) document.getElementById('filter-pool').value = state.pool;
    if (state.distance) document.getElementById('filter-distance').value = state.distance;
    if (state.favorites) document.getElementById('filter-favorites').checked = true;
  } catch (e) { /* ignore corrupt cookie */ }
}

// Haversine distance in miles
function haversine(lat1, lon1, lat2, lon2) {
  const R = 3959; // Earth radius in miles
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function formatTime12(time24) {
  const [h, m] = time24.split(':').map(Number);
  const ampm = h >= 12 ? 'pm' : 'am';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return m === 0 ? `${h12}${ampm}` : `${h12}:${m.toString().padStart(2, '0')}${ampm}`;
}

function calendarParams(slot) {
  return `facility_id=${slot.facility_id}&day=${slot.day_of_week}&start=${encodeURIComponent(slot.start_time)}&type=${encodeURIComponent(slot.swim_type)}`;
}

function render() {
  if (!appData) return;

  const filterType = document.getElementById('filter-type').value;
  const filterDay = document.getElementById('filter-day').value;
  const filterPool = document.getElementById('filter-pool').value;
  const filterDistance = document.getElementById('filter-distance').value;
  const filterFavorites = document.getElementById('filter-favorites').checked;
  const favorites = getFavorites();

  saveFilters();

  // Filter slots
  let filtered = appData.slots.filter(slot => {
    if (filterType && slot.swim_type !== filterType) return false;
    if (filterDay !== '' && slot.day_of_week !== parseInt(filterDay)) return false;
    if (filterPool && slot.facility_id !== parseInt(filterPool)) return false;
    if (filterFavorites && !favorites.includes(slot.facility_id)) return false;

    // Distance filter
    if (filterDistance && userLat !== null) {
      const fac = facilityMap[slot.facility_id];
      if (fac && fac.lat && fac.lon) {
        const dist = haversine(userLat, userLon, fac.lat, fac.lon);
        if (dist > parseFloat(filterDistance)) return false;
      } else {
        return false; // No coordinates, exclude when distance filter is active
      }
    }

    return true;
  });

  // Sort by day, then time, then facility name
  filtered.sort((a, b) => {
    if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week;
    if (a.start_time !== b.start_time) return a.start_time.localeCompare(b.start_time);
    const nameA = (facilityMap[a.facility_id] || {}).name || '';
    const nameB = (facilityMap[b.facility_id] || {}).name || '';
    return nameA.localeCompare(nameB);
  });

  // Group by day
  const grouped = {};
  for (const slot of filtered) {
    const day = slot.day_of_week;
    if (!grouped[day]) grouped[day] = [];
    grouped[day].push(slot);
  }

  const container = document.getElementById('schedule');

  if (filtered.length === 0) {
    container.innerHTML = '<p class="empty">No swim sessions match your filters.</p>';
    return;
  }

  let html = '';
  for (let day = 0; day < 7; day++) {
    const slots = grouped[day];
    if (!slots) continue;

    html += `<div class="day-group"><h2>${DAYS[day]}</h2><div class="slots">`;
    for (const slot of slots) {
      const fac = facilityMap[slot.facility_id] || {};
      const isFav = favorites.includes(slot.facility_id);
      let distStr = '';
      if (userLat !== null && fac.lat && fac.lon) {
        const dist = haversine(userLat, userLon, fac.lat, fac.lon);
        distStr = `<span class="distance">${dist.toFixed(1)} mi</span>`;
      }

      const params = calendarParams(slot);
      html += `
        <div class="slot">
          <div class="slot-main">
            <span class="slot-time">${formatTime12(slot.start_time)}-${formatTime12(slot.end_time)}</span>
            <span class="slot-pool">${fac.name || 'Unknown'}</span>
            ${distStr}
            <span class="slot-type">${slot.swim_type}</span>
            <button class="fav-btn${isFav ? ' is-fav' : ''}" data-fid="${slot.facility_id}" title="${isFav ? 'Remove from favorites' : 'Add to favorites'}">${isFav ? '\u2605' : '\u2606'}</button>
          </div>
          <div class="slot-actions">
            <a href="/api/calendar/ics?${params}" class="cal-link" title="Download .ics">iCal</a>
            <a href="#" class="cal-link gcal-link" data-params="${params}" title="Add to Google Calendar">GCal</a>
          </div>
        </div>`;
    }
    html += '</div></div>';
  }
  container.innerHTML = html;

  // Attach event listeners
  for (const btn of container.querySelectorAll('.fav-btn')) {
    btn.addEventListener('click', () => toggleFavorite(parseInt(btn.dataset.fid)));
  }
  for (const link of container.querySelectorAll('.gcal-link')) {
    link.addEventListener('click', async (e) => {
      e.preventDefault();
      const resp = await fetch('/api/calendar/google?' + link.dataset.params);
      const data = await resp.json();
      if (data.url) window.open(data.url, '_blank');
    });
  }
}

async function init() {
  const resp = await fetch('/api/data');
  appData = await resp.json();

  // Build facility map
  for (const fac of appData.facilities) {
    facilityMap[fac.id] = fac;
  }

  // Populate swim type filter
  const typeSelect = document.getElementById('filter-type');
  for (const t of appData.swim_types) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    typeSelect.appendChild(opt);
  }

  // Populate pool filter
  const poolSelect = document.getElementById('filter-pool');
  for (const fac of appData.facilities) {
    const opt = document.createElement('option');
    opt.value = fac.id;
    opt.textContent = fac.name;
    poolSelect.appendChild(opt);
  }

  loadFilters();

  // Filter event listeners
  for (const id of ['filter-type', 'filter-day', 'filter-pool', 'filter-distance']) {
    document.getElementById(id).addEventListener('change', render);
  }
  document.getElementById('filter-favorites').addEventListener('change', render);

  // Geolocation
  document.getElementById('btn-locate').addEventListener('click', () => {
    const status = document.getElementById('location-status');
    status.textContent = 'Locating...';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userLat = pos.coords.latitude;
        userLon = pos.coords.longitude;
        status.textContent = 'Location set';
        document.getElementById('distance-row').hidden = false;
        render();
      },
      (err) => {
        status.textContent = 'Location denied';
      }
    );
  });

  render();
}

init();
