const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

function getAuthHeaders() {
  const headers = {
    "Content-Type": "application/json",
  };

  const initData = tg?.initData || "";
  if (initData) {
    headers["Authorization"] = `tma ${initData}`;
  } else {
    // Check URL search params for debug_user_id in development mode
    const urlParams = new URLSearchParams(window.location.search);
    const debugUserId = urlParams.get("debug_user_id");
    if (debugUserId) {
      headers["X-Debug-User-Id"] = debugUserId;
    }
  }

  return headers;
}

async function request(endpoint, options = {}) {
  const url = endpoint.startsWith("http") ? endpoint : endpoint;
  const config = {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers || {}),
    },
  };

  const response = await fetch(url, config);

  if (response.status === 401 || response.status === 403) {
    throw new Error("UNAUTHORIZED");
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail?.message || errorData.message || `Request failed with status ${response.status}`);
  }

  return await response.json();
}

export const api = {
  getMe: () => request("/api/me"),
  getMetaRegions: () => request("/api/meta/regions"),
  getStatsSummary: () => request("/api/stats/summary"),
  getStatsDaily: (days = 30) => request(`/api/stats/daily?days=${days}`),
  getStatsRegions: (level = "viloyat", parent = "") =>
    request(`/api/stats/regions?level=${level}&parent=${encodeURIComponent(parent)}`),

  getStores: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.append(k, v);
    });
    return request(`/api/stores?${q.toString()}`);
  },

  getStoresMap: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.append(k, v);
    });
    return request(`/api/stores/map?${q.toString()}`);
  },

  getStoreDetail: (id) => request(`/api/stores/${id}`),
  deleteStore: (id) => request(`/api/stores/${id}`, { method: "DELETE" }),

  getAgents: () => request("/api/agents"),
  getAgentsRanking: (period = "day") => request(`/api/agents/ranking?period=${period}`),

  approveAgent: (id) => request(`/api/agents/${id}/approve`, { method: "POST" }),
  blockAgent: (id) => request(`/api/agents/${id}/block`, { method: "POST" }),
  unblockAgent: (id) => request(`/api/agents/${id}/unblock`, { method: "POST" }),
  updateAgentPlan: (id, daily_plan) =>
    request(`/api/agents/${id}/plan`, {
      method: "POST",
      body: JSON.stringify({ daily_plan: parseInt(daily_plan, 10) }),
    }),

  exportExcel: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.append(k, v);
    });
    return request(`/api/export/excel?${q.toString()}`, { method: "POST" });
  },
};
