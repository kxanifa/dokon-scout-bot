const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
  } catch (e) {
    // ignore
  }
}

// Check URL parameters for direct auth token (e.g. from Telegram bot /admin link)
try {
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get("auth_token") || urlParams.get("token");
  if (tokenFromUrl) {
    localStorage.setItem("dokon_admin_token", tokenFromUrl);
    urlParams.delete("auth_token");
    urlParams.delete("token");
    const cleanUrl = window.location.pathname + (urlParams.toString() ? "?" + urlParams.toString() : "");
    window.history.replaceState({}, document.title, cleanUrl);
  }
} catch (e) {
  console.warn("URL token parse error:", e);
}

function getAuthHeaders() {
  const headers = {
    "Content-Type": "application/json",
  };

  const initData = tg?.initData || "";
  if (initData) {
    headers["Authorization"] = `tma ${initData}`;
    return headers;
  }

  const storedToken = localStorage.getItem("dokon_admin_token");
  if (storedToken) {
    headers["Authorization"] = `Bearer ${storedToken}`;
    return headers;
  }

  // Check URL search params for debug_user_id in development mode
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const debugUserId = urlParams.get("debug_user_id");
    if (debugUserId) {
      headers["X-Debug-User-Id"] = debugUserId;
    }
  } catch (e) {
    // ignore
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
    if (!tg?.initData) {
      window.dispatchEvent(
        new CustomEvent("app:unauthorized", {
          detail: { endpoint, status: response.status },
        })
      );
    }
    throw new Error("UNAUTHORIZED");
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail?.message || errorData.message || `Request failed with status ${response.status}`);
  }

  return await response.json();
}

export const api = {
  login: async (secret) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret: secret.trim() }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || "Maxfiy kalit noto'g'ri");
    }
    const data = await res.json();
    if (data.token) {
      localStorage.setItem("dokon_admin_token", data.token);
    }
    return data;
  },
  logout: () => {
    localStorage.removeItem("dokon_admin_token");
    window.location.reload();
  },
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
