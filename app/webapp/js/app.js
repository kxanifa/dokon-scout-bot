import { api } from "./api.js";
import { getTranslation } from "./i18n.js";

const tg = window.Telegram?.WebApp;

// App State
const state = {
  user: null,
  lang: "uz",
  currentTab: "home",
  filters: {
    viloyat: "",
    tuman: "",
    mahalla: "",
    q: "",
  },
  regionsTree: [],
  map: null,
  clusterGroup: null,
  charts: {
    daily: null,
    regions: null,
  },
};

// Security: XSS Sanitization
function escapeHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatStoreDate(rawDate, rawTime) {
  if (!rawDate && !rawTime) return "";
  let dStr = String(rawDate || "").trim();
  if (/^\d{5}(\.\d+)?$/.test(dStr)) {
    const days = parseFloat(dStr);
    const d = new Date(Math.round((days - 25569) * 86400 * 1000));
    if (!isNaN(d.getTime())) {
      dStr = d.toISOString().split("T")[0];
    }
  }
  let tStr = String(rawTime || "").trim();
  if (/^0\.\d+$/.test(tStr)) {
    const totalSecs = Math.round(parseFloat(tStr) * 86400);
    const hours = String(Math.floor(totalSecs / 3600)).padStart(2, "0");
    const mins = String(Math.floor((totalSecs % 3600) / 60)).padStart(2, "0");
    tStr = `${hours}:${mins}`;
  }
  return [dStr, tStr].filter(Boolean).join(" ");
}

function t(key) {
  return getTranslation(key, state.lang);
}

function showToast(message) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 2800);
}

function haptic(type = "light") {
  try {
    if (tg?.HapticFeedback) {
      if (type === "medium") tg.HapticFeedback.impactOccurred("medium");
      else if (type === "success") tg.HapticFeedback.notificationOccurred("success");
      else tg.HapticFeedback.impactOccurred("light");
    }
  } catch (e) {
    // Ignore in desktop/browser test
  }
}

// ------------------ Tab Navigation (Desktop & Mobile) ------------------
const TAB_TITLES = {
  home: { title: "Bosh sahifa", subtitle: "Real vaqtdagi do'konlar va agentlar statistikasi" },
  map: { title: "Do'konlar Xaritasi", subtitle: "Geolokatsiya bo'yicha klasterli xarita" },
  stores: { title: "Do'konlar Ro'yxati", subtitle: "Barcha kiritilgan savdo nuqtalari" },
  agents: { title: "Agentlar Boshqaruvi", subtitle: "Agentlarni tasdiqlash, bloklash va kunlik rejalari" },
  reports: { title: "Hisobotlar & Eksport", subtitle: "Hududlar tahlili va Excel formatida yuklab olish" },
};

function switchTab(tabName) {
  state.currentTab = tabName;
  haptic("light");

  // Update mobile nav
  document.querySelectorAll(".nav-tab").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-tab") === tabName);
  });

  // Update desktop sidebar
  document.querySelectorAll(".sidebar-item").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-tab") === tabName);
  });

  // Switch screens
  document.querySelectorAll(".screen-view").forEach((el) => el.classList.remove("active"));
  const targetScreen = document.getElementById(`${tabName}-screen`);
  if (targetScreen) targetScreen.classList.add("active");

  // Update header titles
  const meta = TAB_TITLES[tabName] || { title: "Do'kon Skaut", subtitle: "Boshqaruv paneli" };
  const titleEl = document.getElementById("page-title");
  const subEl = document.getElementById("page-subtitle");
  if (titleEl) titleEl.textContent = meta.title;
  if (subEl) subEl.textContent = meta.subtitle;

  // Load screen data
  if (tabName === "home") loadHomeScreen();
  else if (tabName === "map") loadMapScreen();
  else if (tabName === "stores") loadStoresScreen();
  else if (tabName === "agents") loadAgentsScreen();
  else if (tabName === "reports") loadReportsScreen();
}

function refreshCurrentScreen() {
  haptic("medium");
  showToast("🔄 Ma'lumotlar yangilanmoqda...");
  switchTab(state.currentTab);
}

function openSpreadsheet() {
  if (state.user?.spreadsheet_url) {
    window.open(state.user.spreadsheet_url, "_blank");
  } else {
    showToast("Google Sheets havolasi yuklanmoqda...");
  }
}

// ------------------ 1. Home Screen ------------------
async function loadHomeScreen() {
  try {
    const summary = await api.getStatsSummary();
    document.getElementById("kpi-total").textContent = Number(summary.total_stores || 0).toLocaleString();
    document.getElementById("kpi-today").textContent = Number(summary.today || 0).toLocaleString();
    document.getElementById("kpi-week").textContent = Number(summary.week || 0).toLocaleString();
    document.getElementById("kpi-active-agents").textContent = Number(summary.active_agents || 0).toLocaleString();

    // Charts
    const dailyData = await api.getStatsDaily(30);
    renderDailyChart(dailyData);

    const regionsData = await api.getStatsRegions("viloyat", "");
    renderRegionsChart(regionsData);

    // Top agents
    const ranking = await api.getAgentsRanking("day");
    const container = document.getElementById("home-top-agents");
    if (container) {
      if (ranking?.ranking_text) {
        container.innerHTML = `<pre style="font-family: inherit; white-space: pre-wrap; font-size: 13px; line-height: 1.6; margin: 0;">${escapeHTML(ranking.ranking_text)}</pre>`;
      } else {
        container.innerHTML = "Bugun hali yangi do'kon kiritilmagan.";
      }
    }
  } catch (e) {
    console.error("Home screen load error:", e);
  }
}

function renderDailyChart(data) {
  const ctx = document.getElementById("chart-daily-canvas");
  if (!ctx || !window.Chart) return;

  if (state.charts.daily) state.charts.daily.destroy();

  const labels = data.map((d) => d.date.slice(5)); // MM-DD
  const values = data.map((d) => d.count);

  state.charts.daily = new window.Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Do'konlar",
          data: values,
          borderColor: "#6366f1",
          backgroundColor: "rgba(99, 102, 241, 0.15)",
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 2.5,
          pointBackgroundColor: "#6366f1",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#64748b", font: { size: 10 } } },
        y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "#64748b", font: { size: 10 } } },
      },
    },
  });
}

function renderRegionsChart(data) {
  const ctx = document.getElementById("chart-regions-canvas");
  if (!ctx || !window.Chart) return;

  if (state.charts.regions) state.charts.regions.destroy();

  const labels = data.map((d) => d.name);
  const values = data.map((d) => d.count);

  state.charts.regions = new window.Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: "rgba(59, 130, 246, 0.8)",
          hoverBackgroundColor: "#3b82f6",
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "#64748b", font: { size: 10 } } },
        y: { grid: { display: false }, ticks: { color: "#94a3b8", font: { size: 11, weight: 600 } } },
      },
    },
  });
}

// ------------------ 2. Map Screen ------------------
async function loadMapScreen() {
  if (!window.L) return;

  if (!state.map) {
    state.map = window.L.map("leaflet-map").setView([41.311081, 69.240562], 11);
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(state.map);

    state.clusterGroup = window.L.markerClusterGroup();
    state.map.addLayer(state.clusterGroup);
  }

  try {
    const points = await api.getStoresMap(state.filters);
    state.clusterGroup.clearLayers();

    const bounds = [];
    points.forEach((p) => {
      const marker = window.L.marker([p.lat, p.lon]);

      // Tooltip on hover
      marker.bindTooltip(escapeHTML(p.name), {
        direction: "top",
        className: "custom-map-tooltip",
        offset: [0, -10],
      });

      // Rich popup on click
      const thumbSrc = p.photo1_id ? `/api/photo/${p.photo1_id}?w=120` : "";
      const thumbHTML = thumbSrc
        ? `<img src="${thumbSrc}" class="map-popup-thumb" alt="${escapeHTML(p.name)}">`
        : `<div class="map-popup-thumb-placeholder">🏪</div>`;

      const formattedPDate = formatStoreDate(p.date, p.time);
      const locStr = [p.district || p.state, p.mahalla].filter(Boolean).join(", ");

      const popupHTML = `
        <div class="map-popup-card">
          <div class="map-popup-header" onclick="window.app.openStoreDetailSheet(${p.id})">
            ${thumbHTML}
            <div class="map-popup-meta">
              <div class="map-popup-title">${escapeHTML(p.name)}</div>
              <div class="map-popup-sub">📍 ${escapeHTML(locStr || "Joylashuv")}</div>
              ${p.phone ? `<div class="map-popup-phone">📞 ${escapeHTML(p.phone)}</div>` : ""}
            </div>
          </div>
          <button type="button" class="map-popup-btn" onclick="window.app.openStoreDetailSheet(${p.id})">
            🔍 Batafsil ma'lumot va rasmlar
          </button>
        </div>
      `;

      marker.bindPopup(popupHTML, {
        className: "custom-leaflet-popup",
        maxWidth: 280,
      });

      state.clusterGroup.addLayer(marker);
      bounds.push([p.lat, p.lon]);
    });

    if (bounds.length > 0) {
      state.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }
  } catch (e) {
    console.error("Map load error:", e);
  }
}

// ------------------ 3. Stores Screen ------------------
let searchDebounceTimeout = null;

async function loadStoresScreen() {
  const container = document.getElementById("stores-list-container");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-secondary);">Yuklanmoqda...</div>`;

  try {
    const data = await api.getStores({ ...state.filters, page: 1, page_size: 60 });
    if (!data.stores || data.stores.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 48px var(--space-4); color: var(--text-secondary);">
          <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
          <div style="font-weight: 700; font-size: 16px; color: var(--text-primary);">Do'konlar topilmadi</div>
          <div style="font-size: 13px; margin-top: 4px;">Qidiruv yoki filtrlarni o'zgartirib ko'ring.</div>
        </div>`;
      return;
    }

    container.innerHTML = data.stores
      .map((s) => {
        const thumbSrc = s.photo1_id ? `/api/photo/${s.photo1_id}?w=120` : "";
        const thumbHTML = thumbSrc
          ? `<img src="${thumbSrc}" style="width: 52px; height: 52px; border-radius: var(--radius-sm); object-fit: cover;" alt="" loading="lazy">`
          : `<div style="width: 52px; height: 52px; border-radius: var(--radius-sm); background: var(--accent-light); display: flex; align-items: center; justify-content: center; font-size: 24px;">🏪</div>`;

        const sDateFormatted = formatStoreDate(s.date, s.time);

        return `
        <div class="store-card" onclick="window.app.openStoreDetailSheet(${s.id})">
          ${thumbHTML}
          <div class="store-main-info">
            <div class="store-name">${escapeHTML(s.name)}</div>
            <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 4px;">
              INN: <b style="color: var(--text-primary);">${escapeHTML(s.inn || "Yo'q")}</b> 
              ${s.phone ? `• <span style="color: var(--accent-color);">${escapeHTML(s.phone)}</span>` : ""}
            </div>
            <div class="store-meta">
              <span>📍 ${escapeHTML(s.district || s.state || "")}, ${escapeHTML(s.mahalla || "")}</span>
              <span class="store-agent-pill">👤 ${escapeHTML(s.agent_name || "Agent")} • 🕒 ${escapeHTML(sDateFormatted || "")}</span>
            </div>
          </div>
          <div style="font-size: 18px; color: var(--text-muted); align-self: center;">›</div>
        </div>
      `;
      })
      .join("");
  } catch (e) {
    container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--danger-color);">${escapeHTML(e.message)}</div>`;
  }
}

function clearStoreFilters() {
  state.filters.viloyat = "";
  state.filters.tuman = "";
  state.filters.q = "";
  const qInput = document.getElementById("store-search-input");
  if (qInput) qInput.value = "";
  const regSel = document.getElementById("filter-region-select");
  if (regSel) regSel.value = "";
  populateDistrictSelect();
  loadStoresScreen();
}

function populateRegionSelects() {
  const regSelect = document.getElementById("filter-region-select");
  if (!regSelect || !state.regionsTree) return;

  const currentVal = regSelect.value;
  regSelect.innerHTML = `<option value="">Barcha viloyatlar</option>`;
  state.regionsTree.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.name;
    opt.textContent = `${r.name} (${r.count})`;
    regSelect.appendChild(opt);
  });
  if (currentVal) regSelect.value = currentVal;
}

function populateDistrictSelect() {
  const distSelect = document.getElementById("filter-district-select");
  if (!distSelect) return;

  distSelect.innerHTML = `<option value="">Barcha tumanlar</option>`;
  if (!state.filters.viloyat) return;

  const regionObj = state.regionsTree.find((r) => r.name === state.filters.viloyat);
  if (regionObj?.districts) {
    regionObj.districts.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.name;
      opt.textContent = `${d.name} (${d.count})`;
      distSelect.appendChild(opt);
    });
  }
}

// ------------------ 4. Agents Screen ------------------
let currentAgentTab = "active"; // active, pending, blocked

async function loadAgentsScreen() {
  const container = document.getElementById("agents-list-container");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-secondary);">Yuklanmoqda...</div>`;

  try {
    const agents = await api.getAgents();
    const filtered = agents.filter((a) => a.status === currentAgentTab);

    if (filtered.length === 0) {
      container.innerHTML = `<div style="text-align: center; padding: 40px var(--space-4); color: var(--text-secondary);">Bu toifada agentlar mavjud emas.</div>`;
      return;
    }

    container.innerHTML = filtered
      .map((a) => {
        let actionButtons = "";
        if (a.status === "pending") {
          actionButtons = `
            <div class="agent-actions" style="margin-top: 10px;">
              <button class="btn btn-success btn-sm" onclick="window.app.approveAgentAction(${a.id})">✅ Tasdiqlash</button>
              <button class="btn btn-danger btn-sm" onclick="window.app.blockAgentAction(${a.id})">❌ Rad etish</button>
            </div>
          `;
        } else if (a.status === "active") {
          const progressPercent = Math.min(100, Math.round(((a.today_count || 0) / (a.daily_plan || 20)) * 100));
          actionButtons = `
            <div style="margin-top: 10px;">
              <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">
                <span>Kunlik reja bajarilishi:</span>
                <b>${a.today_count} / ${a.daily_plan} (${progressPercent}%)</b>
              </div>
              <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.06); border-radius: var(--radius-full); overflow: hidden; margin-bottom: 12px;">
                <div style="width: ${progressPercent}%; height: 100%; background: var(--accent-gradient); border-radius: var(--radius-full);"></div>
              </div>
              <div class="agent-actions">
                <button class="btn btn-secondary btn-sm" onclick="window.app.editPlanAction(${a.id}, ${a.daily_plan})">🎯 Reja: ${a.daily_plan}</button>
                <button class="btn btn-danger btn-sm" onclick="window.app.blockAgentAction(${a.id})">🚫 Bloklash</button>
              </div>
            </div>
          `;
        } else if (a.status === "blocked") {
          actionButtons = `
            <div class="agent-actions" style="margin-top: 10px;">
              <button class="btn btn-success btn-sm" onclick="window.app.unblockAgentAction(${a.id})">♻️ Blokdan chiqarish</button>
            </div>
          `;
        }

        return `
        <div class="agent-card">
          <div class="agent-card-header">
            <div class="agent-identity">
              <div class="agent-avatar">${escapeHTML((a.name || "A")[0].toUpperCase())}</div>
              <div class="agent-name-role">
                <div class="name">${escapeHTML(a.name)}</div>
                <div class="phone">📞 ${escapeHTML(a.phone || "Telefon yo'q")} • @${escapeHTML(a.username || "noma'lum")}</div>
              </div>
            </div>
            <span class="badge badge-${a.status}">${escapeHTML(a.status)}</span>
          </div>

          <div class="agent-stats-row">
            <div>Bugun: <b style="color: var(--accent-color);">${a.today_count || 0}</b></div>
            <div>Hafta: <b style="color: var(--text-primary);">${a.week_count || 0}</b></div>
            <div>Jami: <b style="color: var(--success-color);">${a.total_count || 0}</b></div>
          </div>

          ${actionButtons}
        </div>
      `;
      })
      .join("");
  } catch (e) {
    container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--danger-color);">${escapeHTML(e.message)}</div>`;
  }
}

// ------------------ 5. Reports Screen ------------------
async function loadReportsScreen() {
  const summaryBox = document.getElementById("reports-filter-summary");
  if (!summaryBox) return;

  try {
    const stores = await api.getStores({ ...state.filters, page: 1, page_size: 1 });
    summaryBox.textContent = `Tanlangan parametrlar bo'yicha jami do'konlar: ${Number(stores.total || 0).toLocaleString()} ta`;

    const regions = await api.getMetaRegions();
    const treeContainer = document.getElementById("reports-region-tree");
    if (treeContainer) {
      treeContainer.innerHTML = regions
        .map(
          (st) => `
        <details style="margin-bottom: 10px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 10px 14px;">
          <summary style="font-weight: 700; cursor: pointer; color: var(--text-primary); font-size: 14px;">
            ${escapeHTML(st.name)} <span style="color: var(--accent-color); font-weight: 600;">(${st.count} ta do'kon)</span>
          </summary>
          <div style="padding-left: 18px; margin-top: 8px; border-left: 2px solid var(--border-subtle); margin-left: 6px;">
            ${st.districts
              .map(
                (d) => `
              <div style="font-size: 13px; color: var(--text-secondary); margin: 6px 0;">
                • ${escapeHTML(d.name)}: <b style="color: var(--text-primary);">${d.count} ta</b>
              </div>
            `
              )
              .join("")}
          </div>
        </details>
      `
        )
        .join("");
    }
  } catch (e) {
    console.error("Reports load error:", e);
  }
}

// ------------------ Store Detail Bottom Sheet / Modal ------------------
async function openStoreDetailSheet(storeId) {
  haptic("light");
  const backdrop = document.getElementById("bottom-sheet-backdrop");
  const content = document.getElementById("sheet-content");
  if (!backdrop || !content) return;

  content.innerHTML = `<div style="text-align: center; padding: 48px; color: var(--text-secondary);"><div style="font-size: 32px; margin-bottom: 8px;">⏳</div><div>Do'kon ma'lumotlari yuklanmoqda...</div></div>`;
  backdrop.classList.add("active");

  try {
    const data = await api.getStoreDetail(storeId);
    const s = data.store;
    const visits = data.visits || [];

    const formattedDate = formatStoreDate(s.date, s.time);
    const statusBadge = s.status === "o'chirilgan"
      ? `<span class="badge badge-blocked">🔴 O'chirilgan</span>`
      : `<span class="badge badge-active">🟢 Faol</span>`;

    // Photo Gallery
    const photos = s.photo_urls || [];
    let photosHTML = "";
    if (photos.length > 0) {
      photosHTML = `
        <div class="store-gallery-container">
          <div class="store-gallery-label">
            <span>📸 Rasmlar (${photos.length})</span>
            <span style="font-size: 11px; text-transform: none; color: var(--text-muted); font-weight: 500;">Kattalashtirish uchun bosing</span>
          </div>
          <div class="store-gallery-grid">
            ${photos.map((url, idx) => `
              <div class="store-gallery-item" onclick="window.app.openLightbox('${url}', '${escapeHTML(s.name)} - ${idx + 1}-rasm')">
                <img src="${url}?w=400" alt="Do'kon rasmi" loading="lazy">
                <span class="store-gallery-badge">${idx + 1}-rasm</span>
                <span class="store-gallery-zoom-icon">🔍</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } else {
      photosHTML = `
        <div style="background: rgba(255,255,255,0.02); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md); padding: 14px; text-align: center; color: var(--text-muted); font-size: 13px; margin-bottom: var(--space-4);">
          📷 Do'konga rasm biriktirilmagan
        </div>
      `;
    }

    // Info Grid
    const infoGridHTML = `
      <div class="store-info-grid">
        <div class="store-info-card">
          <div class="store-info-card-label">🏢 Do'kon nomi</div>
          <div class="store-info-card-value">${escapeHTML(s.name)}</div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">🔢 INN raqami</div>
          <div class="store-info-card-value" style="font-family: monospace; letter-spacing: 0.5px;">${escapeHTML(s.inn || "Kiritilmagan")}</div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">📞 Telefon</div>
          <div class="store-info-card-value">
            ${s.phone ? `<a href="tel:${escapeHTML(s.phone)}">📱 ${escapeHTML(s.phone)}</a>` : "<span style='color: var(--text-muted); font-weight: 500;'>Kiritilmagan</span>"}
          </div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">📍 Viloyat</div>
          <div class="store-info-card-value">${escapeHTML(s.state || "—")}</div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">🏛 Tuman / Shahar</div>
          <div class="store-info-card-value">${escapeHTML(s.district || "—")}</div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">🏡 Mahalla / Manzil</div>
          <div class="store-info-card-value">${escapeHTML(s.mahalla || "—")}</div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">👤 Kiritgan agent</div>
          <div class="store-info-card-value">${escapeHTML(s.agent_name || "Agent")} <span style="font-size: 11px; color: var(--text-muted); font-weight: 500;">(ID: ${s.agent_id})</span></div>
        </div>

        <div class="store-info-card">
          <div class="store-info-card-label">📅 Kiritilgan sana</div>
          <div class="store-info-card-value">${formattedDate || "—"}</div>
        </div>
      </div>
    `;

    // Audit Info
    const auditHTML = (s.updated_at || s.updated_by) ? `
      <div class="store-audit-row">
        <div>🔄 <b>Oxirgi o'zgartirish:</b> ${escapeHTML(s.updated_at || "—")}</div>
        ${s.updated_by ? `<div>✍️ <b>Tahrirlagan:</b> ${escapeHTML(s.updated_by)}</div>` : ""}
      </div>
    ` : "";

    // Visits
    const visitsHTML = visits.length > 0 ? `
      <div style="margin-top: 14px; margin-bottom: 14px;">
        <div style="font-weight: 700; margin-bottom: 8px; font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px;">
          🔁 Qayta tashriflar tarixi (${visits.length}):
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          ${visits.map((v) => {
            const vDate = formatStoreDate(v.date, v.time);
            const vPhotoHTML = (v.photo_urls && v.photo_urls[0])
              ? `<img src="${v.photo_urls[0]}?w=100" style="width: 44px; height: 44px; border-radius: var(--radius-sm); object-fit: cover; cursor: pointer;" onclick="window.app.openLightbox('${v.photo_urls[0]}', 'Tashrif rasmi - ${vDate}')" alt="">`
              : "";
            return `
              <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); padding: 10px 12px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                <div style="font-size: 13px;">
                  <div style="font-weight: 700; color: var(--text-primary);">🕒 ${escapeHTML(vDate)}</div>
                  <div style="color: var(--text-secondary); font-size: 12px;">👤 ${escapeHTML(v.agent_name || "Agent")}</div>
                </div>
                ${vPhotoHTML}
              </div>
            `;
          }).join("")}
        </div>
      </div>
    ` : "";

    // Map & Action buttons
    const googleMapsUrl = s.lat && s.lon ? `https://www.google.com/maps?q=${s.lat},${s.lon}` : "#";
    const yandexMapsUrl = s.lat && s.lon ? `https://yandex.com/maps/?pt=${s.lon},${s.lat}&z=16&l=map` : "#";

    const serializedStore = JSON.stringify(s).replace(/'/g, "\\'").replace(/"/g, '&quot;');

    const actionsHTML = `
      <div class="store-actions-grid">
        <a href="${googleMapsUrl}" target="_blank" class="btn btn-secondary">
          🗺 Google Xarita
        </a>
        <a href="${yandexMapsUrl}" target="_blank" class="btn btn-secondary">
          📍 Yandex Xarita
        </a>
        <button type="button" class="btn btn-secondary" onclick="window.app.openStoreEditModal(${serializedStore})">
          ✏️ Tahrirlash
        </button>
        <button type="button" class="btn btn-danger" onclick="window.app.deleteStoreAction(${s.id})">
          🗑 O'chirish
        </button>
      </div>
    `;

    content.innerHTML = `
      <div class="store-detail-header">
        <div>
          <div class="store-detail-title">${escapeHTML(s.name)}</div>
          <div class="store-detail-badges">
            <span class="store-detail-id-badge">ID: #${s.id}</span>
            ${statusBadge}
          </div>
        </div>
        <button type="button" onclick="window.app.closeBottomSheet()" title="Yopish" style="background: rgba(255,255,255,0.08); border: none; color: var(--text-secondary); width: 32px; height: 32px; border-radius: var(--radius-full); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center;">✕</button>
      </div>

      ${photosHTML}
      ${infoGridHTML}
      ${auditHTML}
      ${visitsHTML}
      ${actionsHTML}
    `;
  } catch (e) {
    content.innerHTML = `<div style="color: var(--danger-color); padding: 24px; text-align: center;">${escapeHTML(e.message)}</div>`;
  }
}

// ------------------ Lightbox Functions ------------------
function openLightbox(imgSrc, title = "") {
  haptic("light");
  const modal = document.getElementById("lightbox-modal");
  const img = document.getElementById("lightbox-img");
  const caption = document.getElementById("lightbox-caption");
  if (!modal || !img) return;

  img.src = imgSrc;
  if (caption) caption.textContent = title;
  modal.classList.add("active");
}

function closeLightbox() {
  const modal = document.getElementById("lightbox-modal");
  if (modal) modal.classList.remove("active");
}

// ------------------ Store Edit Modal ------------------
function openStoreEditModal(store) {
  haptic("light");
  const modal = document.getElementById("store-edit-modal");
  if (!modal || !store) return;

  document.getElementById("edit-store-id").value = store.id;
  document.getElementById("edit-store-name").value = store.name || "";
  document.getElementById("edit-store-inn").value = store.inn || "";
  document.getElementById("edit-store-phone").value = store.phone || "";
  document.getElementById("edit-store-mahalla").value = store.mahalla || "";

  modal.classList.add("active");
}

function closeStoreEditModal() {
  const modal = document.getElementById("store-edit-modal");
  if (modal) modal.classList.remove("active");
}

async function submitStoreEdit(event) {
  event.preventDefault();
  haptic("medium");

  const id = parseInt(document.getElementById("edit-store-id").value, 10);
  const name = document.getElementById("edit-store-name").value.trim();
  const inn = document.getElementById("edit-store-inn").value.trim();
  const phone = document.getElementById("edit-store-phone").value.trim();
  const mahalla = document.getElementById("edit-store-mahalla").value.trim();

  const saveBtn = document.getElementById("btn-save-store");
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = "Saqlanmoqda...";
  }

  try {
    await api.updateStore(id, { name, inn, phone, mahalla });
    showToast("✅ Do'kon ma'lumotlari yangilandi!");
    closeStoreEditModal();
    // Reload open detail and screens
    openStoreDetailSheet(id);
    if (state.currentTab === "stores") loadStoresScreen();
    else if (state.currentTab === "map") loadMapScreen();
  } catch (e) {
    alert("Xatolik: " + e.message);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Saqlash 💾";
    }
  }
}

function closeBottomSheet() {
  const backdrop = document.getElementById("bottom-sheet-backdrop");
  if (backdrop) backdrop.classList.remove("active");
}

// ------------------ Actions ------------------
async function deleteStoreAction(id) {
  if (!confirm("Haqiqatan ham bu do'konni o'chirmoqchimisiz?")) return;
  haptic("medium");
  try {
    await api.deleteStore(id);
    showToast("✅ Do'kon o'chirildi.");
    closeBottomSheet();
    if (state.currentTab === "stores") loadStoresScreen();
    else if (state.currentTab === "map") loadMapScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function approveAgentAction(id) {
  haptic("medium");
  try {
    await api.approveAgent(id);
    showToast("✅ Agent tasdiqlandi!");
    loadAgentsScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function blockAgentAction(id) {
  if (!confirm("Agentni bloklamoqchimisiz?")) return;
  haptic("medium");
  try {
    await api.blockAgent(id);
    showToast("🚫 Agent bloklandi.");
    loadAgentsScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function unblockAgentAction(id) {
  haptic("medium");
  try {
    await api.unblockAgent(id);
    showToast("♻️ Agent blokdan chiqarildi.");
    loadAgentsScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function editPlanAction(id, currentPlan) {
  const newPlan = prompt("Yangi kunlik rejani kiriting:", currentPlan || 20);
  if (!newPlan || isNaN(newPlan)) return;
  haptic("medium");
  try {
    await api.updateAgentPlan(id, newPlan);
    showToast("🎯 Reja yangilandi!");
    loadAgentsScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function exportExcelAction() {
  const btn = document.getElementById("btn-export-excel");
  if (btn) btn.disabled = true;
  showToast("⏳ Excel fayl tayyorlanmoqda...");
  haptic("medium");

  try {
    await api.exportExcel(state.filters);
    showToast("✅ Fayl Telegram botingizga yuborildi!");
  } catch (e) {
    alert(`Xatolik: ${e.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ------------------ Authentication Modal Handling ------------------
function showLoginModal() {
  const modal = document.getElementById("login-modal");
  if (modal) modal.classList.add("active");
}

function hideLoginModal() {
  const modal = document.getElementById("login-modal");
  if (modal) modal.classList.remove("active");
}

function togglePasswordVisibility() {
  const input = document.getElementById("login-secret-input");
  const btn = document.getElementById("toggle-pwd-btn");
  if (!input || !btn) return;

  if (input.type === "password") {
    input.type = "text";
    btn.textContent = "🙈";
  } else {
    input.type = "password";
    btn.textContent = "👁";
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const input = document.getElementById("login-secret-input");
  const btn = document.getElementById("login-submit-btn");
  const errorMsg = document.getElementById("login-error-msg");
  if (!input || !btn) return;

  const secret = input.value.trim();
  if (!secret) return;

  btn.disabled = true;
  btn.textContent = "Tekshirilmoqda...";
  if (errorMsg) errorMsg.style.display = "none";

  try {
    await api.login(secret);
    hideLoginModal();
    showToast("✅ Muvaffaqiyatli kirildi!");
    await initApp();
  } catch (err) {
    if (errorMsg) {
      errorMsg.textContent = err.message || "Maxfiy kalit noto'g'ri.";
      errorMsg.style.display = "block";
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "Kirish 🚀";
  }
}

// ------------------ Live Tashkent Clock ------------------
function initLiveClock() {
  const clockEl = document.getElementById("tashkent-time");
  if (!clockEl) return;

  function update() {
    const now = new Date();
    // Tashkent is UTC+5
    const utc = now.getTime() + now.getTimezoneOffset() * 60000;
    const tashkentTime = new Date(utc + 3600000 * 5);
    const h = String(tashkentTime.getHours()).padStart(2, "0");
    const m = String(tashkentTime.getMinutes()).padStart(2, "0");
    const s = String(tashkentTime.getSeconds()).padStart(2, "0");
    clockEl.textContent = `${h}:${m}:${s}`;
  }

  update();
  setInterval(update, 1000);
}

// ------------------ App Initialization ------------------
async function initApp() {
  // Catch unauthorized events to prompt login modal
  window.addEventListener("app:unauthorized", () => {
    showLoginModal();
  });

  // Mobile Navigation listeners
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabName = tab.getAttribute("data-tab");
      switchTab(tabName);
    });
  });

  // Desktop Sidebar listeners
  document.querySelectorAll(".sidebar-item").forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabName = tab.getAttribute("data-tab");
      switchTab(tabName);
    });
  });

  // Search input listener
  const searchInput = document.getElementById("store-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchDebounceTimeout);
      searchDebounceTimeout = setTimeout(() => {
        state.filters.q = e.target.value;
        loadStoresScreen();
      }, 300);
    });
  }

  // Filter dropdown listeners
  const regSelect = document.getElementById("filter-region-select");
  if (regSelect) {
    regSelect.addEventListener("change", (e) => {
      state.filters.viloyat = e.target.value;
      state.filters.tuman = "";
      populateDistrictSelect();
      loadStoresScreen();
    });
  }

  const distSelect = document.getElementById("filter-district-select");
  if (distSelect) {
    distSelect.addEventListener("change", (e) => {
      state.filters.tuman = e.target.value;
      loadStoresScreen();
    });
  }

  // Agents segment buttons
  document.querySelectorAll(".segment-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".segment-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentAgentTab = btn.getAttribute("data-status");
      loadAgentsScreen();
    });
  });

  // Close sheet on backdrop click
  const backdrop = document.getElementById("bottom-sheet-backdrop");
  if (backdrop) {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) closeBottomSheet();
    });
  }

  // Start Live Tashkent Clock
  initLiveClock();

  // Load user info
  try {
    const me = await api.getMe();
    state.user = me;
    state.lang = me.lang || "uz";
    
    const userRoleBadge = document.getElementById("user-role-badge");
    if (userRoleBadge) userRoleBadge.textContent = me.role;

    const sidebarName = document.getElementById("sidebar-admin-name");
    const sidebarRole = document.getElementById("sidebar-admin-role");
    if (sidebarName) sidebarName.textContent = me.name || "SuperAdmin";
    if (sidebarRole) sidebarRole.textContent = (me.role || "superadmin").toUpperCase();

    hideLoginModal();
  } catch (e) {
    if (e.message === "UNAUTHORIZED") {
      showLoginModal();
      return;
    }
  }

  // Load Regions Tree for filters
  try {
    state.regionsTree = await api.getMetaRegions();
    populateRegionSelects();
  } catch (e) {
    console.error("Regions load error:", e);
  }

  // Global ESC key listener to close modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeLightbox();
      closeStoreEditModal();
      closeBottomSheet();
    }
  });

  // Initial tab load
  switchTab("home");
}

// Export to window for inline onclick handlers
window.app = {
  openStoreDetailSheet,
  closeBottomSheet,
  deleteStoreAction,
  openLightbox,
  closeLightbox,
  openStoreEditModal,
  closeStoreEditModal,
  submitStoreEdit,
  approveAgentAction,
  blockAgentAction,
  unblockAgentAction,
  editPlanAction,
  exportExcelAction,
  handleLogin,
  togglePasswordVisibility,
  refreshCurrentScreen,
  openSpreadsheet,
  clearStoreFilters,
};

window.addEventListener("DOMContentLoaded", initApp);
