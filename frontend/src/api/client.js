const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text };
    }
  }

  if (!response.ok) {
    const detail = payload?.detail || `Request failed (${response.status})`;
    throw new Error(detail);
  }

  return payload;
}

export async function health() {
  return request("/health");
}

export async function runDebate(body) {
  return request("/debates/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listPersonas() {
  return request("/personas");
}

export async function upsertPersona(key, payload) {
  return request(`/personas/${encodeURIComponent(key)}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deletePersona(key) {
  return request(`/personas/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}

export async function listSessions() {
  return request("/sessions");
}

export async function saveSession(payload) {
  return request("/sessions/save", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loadSession(name) {
  return request(`/sessions/${encodeURIComponent(name)}`);
}

export async function deleteSession(name) {
  return request(`/sessions/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}
