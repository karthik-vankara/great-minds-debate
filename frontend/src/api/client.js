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

export async function streamDebate(body, onEvent, onError) {
  /**
   * Stream debate updates via Server-Sent Events (SSE).
   * Uses fetch with streaming Response to handle event stream.
   * 
   * @param {Object} body - DebateRequest payload
   * @param {Function} onEvent - Callback called for each event: (eventData) => void
   * @param {Function} onError - Callback called on error: (error) => void
   * @returns {Function} Unsubscribe function to close the stream
   */
  let isAborted = false;
  let reader = null;
  
  try {
    const response = await fetch(`${API_BASE}/debates/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const text = await response.text();
      let detail = `Stream failed (${response.status})`;
      try {
        const payload = JSON.parse(text);
        detail = payload?.detail || detail;
      } catch {}
      throw new Error(detail);
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const processStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done || isAborted) {
            if (!isAborted) {
              onEvent({ node: "stream_complete" });
            }
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          
          // Keep the last incomplete line in buffer
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const jsonStr = line.slice(6); // Remove "data: " prefix
                const data = JSON.parse(jsonStr);
                if (!isAborted) {
                  onEvent(data);
                }
              } catch (err) {
                if (!isAborted) {
                  onError(new Error(`Failed to parse SSE event: ${err.message}`));
                }
              }
            }
          }
        }
      } catch (err) {
        if (!isAborted) {
          onError(err);
        }
      }
    };

    processStream().catch(() => {
      // Stream processing error already handled in processStream
    });

    // Return unsubscribe/cleanup function
    return () => {
      isAborted = true;
      if (reader) {
        reader.cancel().catch(() => {});
      }
    };
  } catch (err) {
    onError(err);
    return () => {}; // No-op cleanup
  }
}
