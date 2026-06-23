// SwimChi - client-side filtering and rendering

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

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
    if (state.pool) document.getElementById('filter-pool').value = state.pool;
    if (state.distance) document.getElementById('filter-distance').value = state.distance;
    if (state.favorites) document.getElementById('filter-favorites').checked = true;
  } catch (e) { /* ignore corrupt cookie */ }
}

// Haversine distance in miles
function haversine(lat1, lon1, lat2, lon2) {
  const R = 3959;
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

// Local ISO date string (YYYY-MM-DD) using local time, not UTC
function localIso(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

// Convert JS getDay() (0=Sun) to app day_of_week (0=Mon)
function jsDayToAppDay(jsDay) {
  return (jsDay + 6) % 7;
}

function render() {
  if (!appData) return;

  const filterType = document.getElementById('filter-type').value;
  const filterPool = document.getElementById('filter-pool').value;
  const filterDistance = document.getElementById('filter-distance').value;
  const filterFavorites = document.getElementById('filter-favorites').checked;
  const favorites = getFavorites();

  saveFilters();

  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();

  // Build next 7 calendar days starting today
  const upcomingDays = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() + i);
    upcomingDays.push(d);
  }

  const container = document.getElementById('schedule');
  let html = '';
  let totalShown = 0;

  for (const dayDate of upcomingDays) {
    const dayOfWeek = jsDayToAppDay(dayDate.getDay());
    const isoDate = localIso(dayDate);
    const isToday = isoDate === localIso(now);

    const daySlots = appData.slots.filter(slot => {
      if (slot.day_of_week !== dayOfWeek) return false;
      if (filterType && slot.swim_type !== filterType) return false;
      if (filterPool && slot.facility_id !== parseInt(filterPool)) return false;
      if (filterFavorites && !favorites.includes(slot.facility_id)) return false;

      if (filterDistance && userLat !== null) {
        const fac = facilityMap[slot.facility_id];
        if (fac && fac.lat && fac.lon) {
          if (haversine(userLat, userLon, fac.lat, fac.lon) > parseFloat(filterDistance)) return false;
        } else {
          return false;
        }
      }

      // Exclude if outside this facility's schedule date range
      const fac = facilityMap[slot.facility_id];
      if (fac) {
        if (fac.schedule_date_start && isoDate < fac.schedule_date_start) return false;
        if (fac.schedule_date_end && isoDate > fac.schedule_date_end) return false;
      }

      return true;
    });

    daySlots.sort((a, b) => {
      if (a.start_time !== b.start_time) return a.start_time.localeCompare(b.start_time);
      const nameA = (facilityMap[a.facility_id] || {}).name || '';
      const nameB = (facilityMap[b.facility_id] || {}).name || '';
      return nameA.localeCompare(nameB);
    });

    if (daySlots.length === 0) continue;
    totalShown += daySlots.length;

    const dayLabel = isToday ? 'Today' : DAYS[dayOfWeek];
    const dateLabel = dayDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    html += `<div class="mb-6">
      <h2 class="text-lg font-semibold text-brand border-b-2 border-brand pb-1 mb-2">
        ${dayLabel} <span class="text-gray-400 font-normal text-base">— ${dateLabel}</span>
      </h2>`;

    for (const slot of daySlots) {
      const fac = facilityMap[slot.facility_id] || {};
      const isFav = favorites.includes(slot.facility_id);

      const slotStartMinutes = parseInt(slot.start_time.split(':')[0]) * 60 + parseInt(slot.start_time.split(':')[1]);
      const isElapsed = isToday && slotStartMinutes < nowMinutes;

      let distStr = '';
      if (userLat !== null && fac.lat && fac.lon) {
        const dist = haversine(userLat, userLon, fac.lat, fac.lon);
        distStr = `<span class="text-xs text-gray-400 whitespace-nowrap">${dist.toFixed(1)} mi</span>`;
      }

      const params = calendarParams(slot);
      const favColor = isFav ? 'text-amber-400' : 'text-gray-300';
      const elapsedClass = isElapsed ? 'opacity-40' : '';

      html += `
        <div class="bg-white rounded-lg px-3 py-2.5 mb-1.5 shadow-sm flex flex-wrap sm:flex-nowrap justify-between items-start sm:items-center gap-2 ${elapsedClass}">
          <div class="flex items-center gap-2 flex-wrap min-w-0">
            <span class="font-semibold text-sm whitespace-nowrap w-28">${formatTime12(slot.start_time)}–${formatTime12(slot.end_time)}</span>
            <a class="text-sm text-gray-700 hover:underline hover:text-brand min-w-0" href="https://www.chicagoparkdistrict.com/parks-facilities/${fac.slug}" target="_blank">${fac.name || 'Unknown'}</a>
            ${distStr}
            <span class="text-xs bg-blue-50 text-brand px-2 py-0.5 rounded-full whitespace-nowrap">${slot.swim_type}</span>
            <button class="fav-btn text-xl leading-none cursor-pointer bg-transparent border-0 p-0 ${favColor}" data-fid="${slot.facility_id}" title="${isFav ? 'Remove from favorites' : 'Add to favorites'}">${isFav ? '★' : '☆'}</button>
          </div>
          <div class="flex gap-1.5 shrink-0 self-end sm:self-auto">
            <a href="/api/calendar/ics?${params}" class="text-xs text-brand border border-brand px-1.5 py-0.5 rounded whitespace-nowrap hover:bg-brand hover:text-white transition-colors" title="Download .ics">iCal</a>
            <a href="#" class="gcal-link text-xs text-brand border border-brand px-1.5 py-0.5 rounded whitespace-nowrap hover:bg-brand hover:text-white transition-colors" data-params="${params}" title="Add to Google Calendar">GCal</a>
          </div>
        </div>`;
    }
    html += '</div>';
  }

  if (totalShown === 0) {
    container.innerHTML = '<p class="text-center text-gray-400 py-8 text-lg">No swim sessions match your filters.</p>';
    return;
  }

  container.innerHTML = html;

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
  let resp;
  try {
    resp = await fetch('/api/data');
  } catch (e) {
    document.getElementById('schedule').innerHTML =
      '<p class="text-center text-gray-400 py-8 text-lg">You\'re offline. Cached schedules may be shown once the page reloads with cached data.</p>';
    return;
  }
  appData = await resp.json();

  for (const fac of appData.facilities) {
    facilityMap[fac.id] = fac;
  }

  const typeSelect = document.getElementById('filter-type');
  for (const t of appData.swim_types) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    typeSelect.appendChild(opt);
  }

  const poolSelect = document.getElementById('filter-pool');
  for (const fac of appData.facilities) {
    const opt = document.createElement('option');
    opt.value = fac.id;
    opt.textContent = fac.name;
    poolSelect.appendChild(opt);
  }

  loadFilters();

  for (const id of ['filter-type', 'filter-pool', 'filter-distance']) {
    document.getElementById(id).addEventListener('change', render);
  }
  document.getElementById('filter-favorites').addEventListener('change', render);

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
      () => {
        status.textContent = 'Location denied';
      }
    );
  });

  render();
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}

init();
