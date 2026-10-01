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
  setTimeout(() => toast.remove(), 2600);
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

// ------------------ Router & Tab Navigation ------------------
function switchTab(tabName) {
  state.currentTab = tabName;
  haptic("light");

  document.querySelectorAll(".screen-view").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach((el) => el.classList.remove("active"));

  const targetScreen = document.getElementById(`${tabName}-screen`);
  const targetTab = document.querySelector(`.nav-tab[data-tab="${tabName}"]`);

  if (targetScreen) targetScreen.classList.add("active");
  if (targetTab) targetTab.classList.add("active");

  // Load screen data
  if (tabName === "home") loadHomeScreen();
  else if (tabName === "map") loadMapScreen();
  else if (tabName === "stores") loadStoresScreen();
  else if (tabName === "agents") loadAgentsScreen();
  else if (tabName === "reports") loadReportsScreen();
}

// ------------------ 1. Home Screen ------------------
async function loadHomeScreen() {
  try {
    const summary = await api.getStatsSummary();
    document.getElementById("kpi-total").textContent = summary.total_stores || 0;
    document.getElementById("kpi-today").textContent = summary.today || 0;
    document.getElementById("kpi-week").textContent = summary.week || 0;
    document.getElementById("kpi-active-agents").textContent = summary.active_agents || 0;

    // Charts
    const dailyData = await api.getStatsDaily(30);
    renderDailyChart(dailyData);

    const regionsData = await api.getStatsRegions("viloyat", "");
    renderRegionsChart(regionsData);

    // Top 3 agents today
    const ranking = await api.getAgentsRanking("day");
    const container = document.getElementById("home-top-agents");
    if (container && ranking.ranking_text) {
      container.innerHTML = `<pre style="font-family: inherit; white-space: pre-wrap; font-size: 13px;">${escapeHTML(ranking.ranking_text)}</pre>`;
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
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.1)",
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" } },
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
          backgroundColor: "#3b82f6",
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
        x: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { grid: { display: false } },
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
      marker.on("click", () => openStoreDetailSheet(p.id));
      state.clusterGroup.addLayer(marker);
      bounds.push([p.lat, p.lon]);
    });

    if (bounds.length > 0) {
      state.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
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

  container.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--text-secondary);">Yuklanmoqda...</div>`;

  try {
    const data = await api.getStores({ ...state.filters, page: 1, page_size: 50 });
    if (!data.stores || data.stores.length === 0) {
      container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-secondary);">Do'konlar topilmadi.</div>`;
      return;
    }

    container.innerHTML = data.stores
      .map((s) => {
        const thumbSrc = s.photo1_id ? `/api/photo/${s.photo1_id}?w=120` : "";
        const thumbHTML = thumbSrc
          ? `<img src="${thumbSrc}" class="store-thumb" alt="" loading="lazy">`
          : `<div class="store-thumb">🏪</div>`;

        return `
        <div class="store-card" onclick="window.app.openStoreDetailSheet(${s.id})">
          ${thumbHTML}
          <div class="store-info">
            <div class="store-name">${escapeHTML(s.name)}</div>
            <div class="store-inn">INN: ${escapeHTML(s.inn)} ${s.phone ? "• " + escapeHTML(s.phone) : ""}</div>
            <div class="store-meta">📍 ${escapeHTML(s.district)}, ${escapeHTML(s.mahalla)}</div>
            <div class="store-meta">👤 ${escapeHTML(s.agent_name)} • 🕒 ${escapeHTML(s.date)}</div>
          </div>
        </div>
      `;
      })
      .join("");
  } catch (e) {
    container.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--danger-color);">${escapeHTML(e.message)}</div>`;
  }
}

// ------------------ 4. Agents Screen ------------------
let currentAgentTab = "active"; // active, pending, blocked

async function loadAgentsScreen() {
  const container = document.getElementById("agents-list-container");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--text-secondary);">Yuklanmoqda...</div>`;

  try {
    const agents = await api.getAgents();
    const filtered = agents.filter((a) => a.status === currentAgentTab);

    if (filtered.length === 0) {
      container.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-secondary);">Bu bo'limda agentlar yo'q.</div>`;
      return;
    }

    container.innerHTML = filtered
      .map((a) => {
        let actionButtons = "";
        if (a.status === "pending") {
          actionButtons = `
            <div style="display: flex; gap: 8px; margin-top: 10px;">
              <button class="btn btn-primary" style="height: 36px; font-size: 12px;" onclick="window.app.approveAgentAction(${a.id})">✅ Qabul</button>
              <button class="btn btn-danger" style="height: 36px; font-size: 12px;" onclick="window.app.blockAgentAction(${a.id})">❌ Rad</button>
            </div>
          `;
        } else if (a.status === "active") {
          actionButtons = `
            <div style="display: flex; gap: 8px; margin-top: 10px;">
              <button class="btn btn-secondary" style="height: 36px; font-size: 12px;" onclick="window.app.editPlanAction(${a.id}, ${a.daily_plan})">🎯 Reja: ${a.daily_plan}</button>
              <button class="btn btn-danger" style="height: 36px; font-size: 12px;" onclick="window.app.blockAgentAction(${a.id})">🚫 Bloklash</button>
            </div>
          `;
        } else if (a.status === "blocked") {
          actionButtons = `
            <div style="margin-top: 10px;">
              <button class="btn btn-primary" style="height: 36px; font-size: 12px;" onclick="window.app.unblockAgentAction(${a.id})">♻️ Blokdan chiqarish</button>
            </div>
          `;
        }

        return `
        <div class="glass-card" style="margin-bottom: 12px; padding: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
              <div style="font-weight: 700; font-size: 16px;">${escapeHTML(a.name)}</div>
              <div style="font-size: 13px; color: var(--text-secondary);">📞 ${escapeHTML(a.phone)} • @${escapeHTML(a.username || "yo'q")}</div>
              <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">ID: <code>${a.id}</code> • Rol: ${escapeHTML(a.role)}</div>
            </div>
            <span class="badge badge-${a.status}">${escapeHTML(a.status)}</span>
          </div>
          <div style="display: flex; justify-content: space-between; background: var(--bg-secondary); border-radius: 8px; padding: 8px 12px; margin-top: 10px; font-size: 12px;">
            <div>Bugun: <b>${a.today_count}</b></div>
            <div>Hafta: <b>${a.week_count}</b></div>
            <div>Jami: <b>${a.total_count}</b></div>
          </div>
          ${actionButtons}
        </div>
      `;
      })
      .join("");
  } catch (e) {
    container.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--danger-color);">${escapeHTML(e.message)}</div>`;
  }
}

// ------------------ 5. Reports Screen ------------------
async function loadReportsScreen() {
  const summaryBox = document.getElementById("reports-filter-summary");
  if (!summaryBox) return;

  try {
    const stores = await api.getStores({ ...state.filters, page: 1, page_size: 1 });
    summaryBox.textContent = `Tanlangan parametrlar bo'yicha jami do'konlar: ${stores.total || 0} ta`;

    // Render region tree breakdown
    const regions = await api.getMetaRegions();
    const treeContainer = document.getElementById("reports-region-tree");
    if (treeContainer) {
      treeContainer.innerHTML = regions
        .map(
          (st) => `
        <details style="margin-bottom: 8px; background: var(--bg-secondary); border-radius: 8px; padding: 8px 12px;">
          <summary style="font-weight: 600; cursor: pointer;">${escapeHTML(st.name)} (${st.count} ta)</summary>
          <div style="padding-left: 14px; margin-top: 6px;">
            ${st.districts
              .map(
                (d) => `
              <div style="font-size: 13px; color: var(--text-secondary); margin: 3px 0;">
                • ${escapeHTML(d.name)}: <b>${d.count} ta</b>
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

// ------------------ Store Detail Bottom Sheet ------------------
async function openStoreDetailSheet(storeId) {
  haptic("light");
  const backdrop = document.getElementById("bottom-sheet-backdrop");
  const content = document.getElementById("sheet-content");
  if (!backdrop || !content) return;

  content.innerHTML = `<div style="text-align: center; padding: 30px;">Yuklanmoqda...</div>`;
  backdrop.classList.add("active");

  try {
    const data = await api.getStoreDetail(storeId);
    const s = data.store;
    const visits = data.visits || [];

    const photosHTML =
      s.photo_urls && s.photo_urls.length > 0
        ? `<div style="display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 12px;">
            ${s.photo_urls.map((url) => `<img src="${url}?w=400" style="height: 180px; border-radius: 12px; object-fit: cover;" alt="">`).join("")}
           </div>`
        : "";

    const visitsHTML =
      visits.length > 0
        ? `<div style="margin-top: 14px;">
            <div style="font-weight: 600; margin-bottom: 6px;">🔁 Qayta tashriflar tarixi (${visits.length} ta):</div>
            ${visits
              .map(
                (v) => `
              <div style="background: var(--bg-primary); padding: 8px 12px; border-radius: 8px; margin-bottom: 6px; font-size: 12px;">
                🕒 <b>${escapeHTML(v.date)} ${escapeHTML(v.time)}</b> — ${escapeHTML(v.agent_name)}
              </div>
            `
              )
              .join("")}
           </div>`
        : "";

    content.innerHTML = `
      <div style="font-size: 20px; font-weight: 700; margin-bottom: 4px;">${escapeHTML(s.name)}</div>
      <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 12px;">№${s.id} • INN: <b>${escapeHTML(s.inn)}</b></div>

      ${photosHTML}

      <div style="display: flex; flex-direction: column; gap: 6px; font-size: 14px;">
        <div>📍 <b>Hudud:</b> ${escapeHTML(s.state)}, ${escapeHTML(s.district)}, ${escapeHTML(s.mahalla)}</div>
        <div>📞 <b>Telefon:</b> ${s.phone ? `<a href="tel:${escapeHTML(s.phone)}" style="color: var(--accent-color);">${escapeHTML(s.phone)}</a>` : "Kiritilmagan"}</div>
        <div>👤 <b>Agent:</b> ${escapeHTML(s.agent_name)} (<code>${s.agent_id}</code>)</div>
        <div>📅 <b>Kiritilgan:</b> ${escapeHTML(s.date)} ${escapeHTML(s.time)}</div>
      </div>

      ${visitsHTML}

      <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 16px;">
        <a href="https://www.google.com/maps?q=${s.lat},${s.lon}" target="_blank" class="btn btn-secondary" style="text-decoration: none;">
          📍 Google Maps'da ochish
        </a>
        <button class="btn btn-danger" onclick="window.app.deleteStoreAction(${s.id})">
          🗑 O'chirish
        </button>
      </div>
    `;
  } catch (e) {
    content.innerHTML = `<div style="color: var(--danger-color); padding: 20px;">${escapeHTML(e.message)}</div>`;
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
    showToast("Do'kon o'chirildi.");
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
    showToast("Agent tasdiqlandi!");
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
    showToast("Agent bloklandi.");
    loadAgentsScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function unblockAgentAction(id) {
  haptic("medium");
  try {
    await api.unblockAgent(id);
    showToast("Agent blokdan chiqarildi.");
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
    showToast("Reja yangilandi!");
    loadAgentsScreen();
  } catch (e) {
    alert(e.message);
  }
}

async function exportExcelAction() {
  const btn = document.getElementById("btn-export-excel");
  if (btn) btn.disabled = true;
  showToast("⏳ Excel fayl bot chatiga yuborilmoqda...");
  haptic("medium");

  try {
    await api.exportExcel(state.filters);
    showToast("✅ Fayl Telegram chatga yuborildi!");
  } catch (e) {
    alert(`Xatolik: ${e.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ------------------ App Initialization ------------------
async function initApp() {
  // Navigation listeners
  document.querySelectorAll(".nav-tab").forEach((tab) => {
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

  // Load user info
  try {
    const me = await api.getMe();
    state.user = me;
    state.lang = me.lang || "uz";
    const userRoleBadge = document.getElementById("user-role-badge");
    if (userRoleBadge) userRoleBadge.textContent = me.role;
  } catch (e) {
    console.warn("Auth initialization note:", e.message);
  }

  // Load Regions Tree
  try {
    state.regionsTree = await api.getMetaRegions();
  } catch (e) {
    console.error("Regions load error:", e);
  }

  // Initial tab load
  switchTab("home");
}

// Export to window for inline onclick handlers
window.app = {
  openStoreDetailSheet,
  closeBottomSheet,
  deleteStoreAction,
  approveAgentAction,
  blockAgentAction,
  unblockAgentAction,
  editPlanAction,
  exportExcelAction,
};

window.addEventListener("DOMContentLoaded", initApp);
