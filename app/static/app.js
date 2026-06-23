// SwimChi - client-side filtering and rendering

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

let appData = null;
let facilityMap = {};
let userLat = null;
let userLon = null;

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
  favs = favs.includes(facilityId) ? favs.filter(id => id !== facilityId) : [...favs, facilityId];
  setFavorites(favs);
  render();
}

function saveFilters() {
  setCookie('swimchi_filters', JSON.stringify({
    type: document.getElementById('filter-type').value,
    pool: document.getElementById('filter-pool').value,
    distance: document.getElementById('filter-distance').value,
    favorites: document.getElementById('filter-favorites').checked,
  }), 30);
}

function loadFilters() {
  const raw = getCookie('swimchi_filters');
  if (!raw) return;
  try {
    const s = JSON.parse(raw);
    if (s.type) document.getElementById('filter-type').value = s.type;
    if (s.pool) document.getElementById('filter-pool').value = s.pool;
    if (s.distance) document.getElementById('filter-distance').value = s.distance;
    if (s.favorites) document.getElementById('filter-favorites').checked = true;
  } catch (e) {}
}

function haversine(lat1, lon1, lat2, lon2) {
  const R = 3959;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function formatTime12(t) {
  const [h, m] = t.split(':').map(Number);
  const ampm = h >= 12 ? 'pm' : 'am';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return m === 0 ? `${h12}${ampm}` : `${h12}:${m.toString().padStart(2, '0')}${ampm}`;
}

function calendarParams(slot) {
  return `facility_id=${slot.facility_id}&day=${slot.day_of_week}&start=${encodeURIComponent(slot.start_time)}&type=${encodeURIComponent(slot.swim_type)}`;
}

function localIso(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

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

      const fac = facilityMap[slot.facility_id];
      if (fac) {
        if (fac.schedule_date_start && isoDate < fac.schedule_date_start) return false;
        if (fac.schedule_date_end && isoDate > fac.schedule_date_end) return false;
      }

      return true;
    });

    daySlots.sort((a, b) => {
      if (a.start_time !== b.start_time) return a.start_time.localeCompare(b.start_time);
      return ((facilityMap[a.facility_id] || {}).name || '').localeCompare((facilityMap[b.facility_id] || {}).name || '');
    });

    if (daySlots.length === 0) continue;
    totalShown += daySlots.length;

    const dayLabel = isToday ? 'Today' : DAYS[dayOfWeek];
    const dateLabel = dayDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    const hdrColor = isToday ? 'text-orange-500' : 'text-[#0057b7]';
    const hdrBorder = isToday ? 'border-orange-400' : 'border-[#0057b7]';

    html += `<div class="mb-6">
      <div class="flex items-baseline gap-2 border-b-2 ${hdrBorder} pb-2 mb-3">
        <h2 class="text-sm font-bold uppercase tracking-widest ${hdrColor}">${dayLabel}</h2>
        <span class="text-slate-400 text-sm">— ${dateLabel}</span>
      </div>`;

    for (const slot of daySlots) {
      const fac = facilityMap[slot.facility_id] || {};
      const isFav = favorites.includes(slot.facility_id);
      const [sh, sm] = slot.start_time.split(':').map(Number);
      const slotMinutes = sh * 60 + sm;
      const isElapsed = isToday && slotMinutes < nowMinutes;

      const borderColor = isElapsed ? 'border-slate-200' : (isToday ? 'border-orange-400' : 'border-[#0057b7]');
      const cardOpacity = isElapsed ? 'opacity-50' : '';
      const timeStyle = isElapsed ? 'line-through text-slate-400' : 'text-slate-800';
      const favColor = isFav ? 'text-amber-400' : 'text-slate-300';

      let distStr = '';
      if (userLat !== null && fac.lat && fac.lon) {
        const dist = haversine(userLat, userLon, fac.lat, fac.lon);
        distStr = `<span class="text-xs text-slate-400 whitespace-nowrap">${dist.toFixed(1)} mi</span>`;
      }

      const params = calendarParams(slot);

      html += `
        <div class="bg-white rounded-xl border-l-4 ${borderColor} px-3 py-2.5 mb-2 shadow-sm ${cardOpacity}">
          <div class="flex items-center justify-between mb-1">
            <span class="font-mono font-semibold text-sm ${timeStyle}">${formatTime12(slot.start_time)} – ${formatTime12(slot.end_time)}</span>
            <button class="fav-btn text-lg leading-none cursor-pointer bg-transparent border-0 p-0 ml-3 ${favColor}"
                    data-fid="${slot.facility_id}"
                    title="${isFav ? 'Remove from favorites' : 'Add to favorites'}">${isFav ? '★' : '☆'}</button>
          </div>
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
            <a class="text-sm font-medium text-slate-700 hover:text-[#0057b7] hover:underline"
               href="https://www.chicagoparkdistrict.com/parks-facilities/${fac.slug}"
               target="_blank">${fac.name || 'Unknown'}</a>
            <span class="text-xs bg-blue-50 text-[#0057b7] px-2 py-0.5 rounded-full whitespace-nowrap">${slot.swim_type}</span>
            ${distStr}
            <div class="ml-auto flex gap-1.5">
              <a href="/api/calendar/ics?${params}"
                 class="text-xs text-slate-400 border border-slate-200 px-2 py-0.5 rounded hover:text-[#0057b7] hover:border-[#0057b7] transition-colors whitespace-nowrap"
                 title="Download .ics">iCal</a>
              <a href="#"
                 class="gcal-link text-xs text-slate-400 border border-slate-200 px-2 py-0.5 rounded hover:text-[#0057b7] hover:border-[#0057b7] transition-colors whitespace-nowrap"
                 data-params="${params}"
                 title="Add to Google Calendar">GCal</a>
            </div>
          </div>
        </div>`;
    }
    html += '</div>';
  }

  if (totalShown === 0) {
    container.innerHTML = '<p class="text-center text-slate-400 py-12">No swim sessions match your filters.</p>';
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
      '<p class="text-center text-slate-400 py-12">You\'re offline. Check back when connected.</p>';
    return;
  }
  appData = await resp.json();

  for (const fac of appData.facilities) facilityMap[fac.id] = fac;

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
    status.textContent = 'Locating…';
    status.className = 'text-xs text-slate-400';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userLat = pos.coords.latitude;
        userLon = pos.coords.longitude;
        status.textContent = '✓ Set';
        status.className = 'text-xs text-green-600 font-medium';
        document.getElementById('distance-row').hidden = false;
        render();
      },
      () => {
        status.textContent = 'Denied';
        status.className = 'text-xs text-red-500';
      }
    );
  });

  render();
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}

init();
