/**
 * API client — reads JWT from localStorage (local auth), handles 401/403.
 */

// Prod builds MUST set VITE_API_BASE_URL. The localhost fallback is dev-only so
// a misconfigured prod bundle never carries a localhost target (verified by the
// grep-dist check in the deploy runbook).
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
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
  } catch { /* token decode failed — fall through to unauthenticated */ }
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

  async put(path: string, body?: unknown) {
    const headers = getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "PUT",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse(res);
  },

  async getText(path: string): Promise<string> {
    const headers = getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, { headers });
    if (res.status === 401) { handleUnauth(); throw new ApiError(401, "Session expired"); }
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.text();
  },

  async getBlob(path: string): Promise<Blob> {
    // Auth-gated binary GET (e.g. PDF preview). A plain <a href> can't carry the
    // Authorization header, so admin-only downloads must fetch through here.
    const headers = getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, { headers });
    if (res.status === 401) { handleUnauth(); throw new ApiError(401, "Session expired"); }
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.blob();
  },

  async postForm(path: string, formData: FormData) {
    const headers = getAuthHeaders();
    // Remove Content-Type so browser sets multipart boundary automatically
    delete headers["Content-Type"];
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    return handleResponse(res);
  },

  async putForm(path: string, formData: FormData) {
    const headers = getAuthHeaders();
    delete headers["Content-Type"];
    const res = await fetch(`${API_BASE}${path}`, { method: "PUT", headers, body: formData });
    return handleResponse(res);
  },

  async del(path: string) {
    const headers = getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers });
    return handleResponse(res);
  },
};
