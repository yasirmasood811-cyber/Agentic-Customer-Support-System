// Talks to the FastAPI backend. No API keys here, only the backend address.
const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "admin_token";

export class AuthError extends Error {}

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
const setToken = (t) => (t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY));

/**
 * Sends a chat message and calls onEvent(event) for every streamed event
 * (start | route | agent | tool | escalation | status | message | error | done).
 */
export async function streamChat({ message, threadId }, onEvent) {
  const res = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!res.ok || !res.body) throw new Error(`Server error ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n"); // SSE events end with a blank line
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

async function readError(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join("; "); // validation errors
    return `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

// Admin requests carry the login token. A 401 means the login expired.
async function adminRequest(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...(options.headers || {}), Authorization: `Bearer ${getToken() || ""}` },
  });
  if (res.status === 401) {
    setToken(null);
    throw new AuthError("Please log in again.");
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function adminLogin(password) {
  const res = await fetch(`${API}/api/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error(await readError(res));
  const data = await res.json();
  setToken(data.token);
}

export async function adminLogout() {
  try {
    await fetch(`${API}/api/admin/logout`, { method: "POST", headers: { Authorization: `Bearer ${getToken() || ""}` } });
  } finally {
    setToken(null);
  }
}

export const getTickets = () => adminRequest("/api/tickets");
export const getOrders = () => adminRequest("/api/orders");
export const updateTicket = (id, { status, note, notify }) =>
  adminRequest(`/api/tickets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note: note || null, notify }),
  });

export const getCustomers = () => adminRequest("/api/customers");
export const createOrder = (payload) =>
  adminRequest("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
