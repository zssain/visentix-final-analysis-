/**
 * API client — attaches JWT from Supabase session, handles 401/403.
 * Never sends the service-role key.
 */
import { supabase } from "./supabase";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) {
    throw new ApiError(401, "Not authenticated");
  }
  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

async function handleResponse(res: Response) {
  if (res.status === 401) {
    // Token expired — sign out and redirect
    await supabase.auth.signOut();
    window.location.href = "/login";
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
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, { headers });
    return handleResponse(res);
  },

  async post(path: string, body?: unknown) {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse(res);
  },
};
