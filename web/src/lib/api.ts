/**
 * API client — reads JWT from localStorage (local auth), handles 401/403.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const SESSION_KEY = "visentix-auth-session";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getAuthHeaders(): Record<string, string> {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (raw) {
      const session = JSON.parse(raw) as { access_token?: string };
      if (session?.access_token) {
        return {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        };
      }
    }
  } catch {}
  throw new ApiError(401, "Not authenticated");
}

function handleUnauth() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem("visentix-auth-profile");
  window.location.href = "/login";
}

async function handleResponse(res: Response) {
  if (res.status === 401) {
    handleUnauth();
    throw new ApiError(401, "Session expired");
  }
  if (res.status === 403) {
    throw new ApiError(403, "Forbidden — insufficient role");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json();
}

export const api = {
  async get(path: string) {
    const headers = getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, { headers });
    return handleResponse(res);
  },

  async post(path: string, body?: unknown) {
    const headers = getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse(res);
  },
};
