// In dev, Vite proxies /api → http://localhost:8000.
// In production (Render), VITE_API_BASE_URL points to the backend service.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export function getToken() {
  return localStorage.getItem('ma_token');
}

async function req(path, opts = {}) {
  const token = getToken();
  const headers = {
    ...(opts.json !== undefined ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...opts.headers,
  };
  const res = await fetch(BASE_URL + path, {
    ...opts,
    headers,
    body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

export const api = {
  // ── Auth ──────────────────────────────────────────────
  register: (email, password) =>
    req('/api/auth/register', { method: 'POST', json: { email, password } }),

  login: async (email, password) => {
    const res = await fetch(BASE_URL + '/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid credentials');
    }
    return res.json();
  },

  // ── Projects ──────────────────────────────────────────
  getProjects: (page = 1, limit = 20) =>
    req(`/api/projects/?page=${page}&limit=${limit}`),
  createProject: (name, description = '') =>
    req('/api/projects/', { method: 'POST', json: { name, description } }),
  updateProject: (id, data) =>
    req(`/api/projects/${id}`, { method: 'PATCH', json: data }),
  deleteProject: (id) =>
    req(`/api/projects/${id}`, { method: 'DELETE' }),

  // ── Conversations ─────────────────────────────────────
  getConversations: (projectId, page = 1) =>
    req(`/api/conversations/?project_id=${projectId}&page=${page}&limit=20`),
  createConversation: (project_id, mode, initial_message) =>
    req('/api/conversations/', { method: 'POST', json: { project_id, mode, initial_message } }),
  getConversation: (id) =>
    req(`/api/conversations/${id}`),
  sendMessage: (id, message) =>
    req(`/api/conversations/${id}/message`, { method: 'POST', json: { message } }),
  deleteConversation: (id) =>
    req(`/api/conversations/${id}`, { method: 'DELETE' }),

  // ── Metrics ───────────────────────────────────────────
  getMetrics: () => req('/api/metrics'),

  // ── Export & Files ────────────────────────────────────────
  exportProject: (projectId) =>
    fetch(BASE_URL + `/api/projects/${projectId}/export`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    }),

  listProjectFiles: (projectId) =>
    req(`/api/projects/${projectId}/files`),

  // ── Task detail ───────────────────────────────────────────
  getTask: (taskId) =>
    req(`/api/agents/tasks/${taskId}`),
};

// SSE streaming using fetch (EventSource doesn't support custom headers)
export async function* streamConversation(conversationId) {
  const token = getToken();
  let res;
  try {
    res = await fetch(BASE_URL + `/api/conversations/${conversationId}/stream`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch { return; }

  if (!res.ok || !res.body) return;

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)); } catch { /* skip malformed */ }
      }
    }
  }
}
