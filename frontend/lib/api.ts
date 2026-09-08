/**
 * API client.
 *
 * Requests go to same-origin `/api/...`; next.config.mjs proxies them to FastAPI in
 * development, so nothing needs CORS configuration on a reviewer's machine.
 *
 * The active demo role travels in `X-Demo-Role`. Switching roles in the UI changes
 * what the server returns — masking and consent are enforced on the backend, so the
 * buyer view is not a client-side illusion.
 */

import type { Role } from "./domain";

const ROLE_KEY = "ltc.role";

export function getRole(): Role {
  if (typeof window === "undefined") return "BUYER";
  return (window.localStorage.getItem(ROLE_KEY) as Role) || "BUYER";
}

export function setRole(role: Role) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ROLE_KEY, role);
  window.dispatchEvent(new CustomEvent("ltc:role", { detail: role }));
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Where the API lives.
 *
 * Unset (local development): requests go to the same origin and next.config.mjs
 * proxies them to the local backend, so nothing needs CORS configuration.
 *
 * Set (production): requests go straight to the backend. Calling it directly rather
 * than proxying through Vercel avoids the platform's request-body limit on uploads
 * and removes a network hop; the API sets CORS headers for this reason.
 *
 * NEXT_PUBLIC_ variables are inlined at build time, so changing this on Vercel
 * requires a redeploy — not merely a restart.
 */
const CONFIGURED_API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

const BASE =
  typeof window === "undefined"
    ? CONFIGURED_API || "http://127.0.0.1:8000"
    : CONFIGURED_API;

async function request<T>(path: string, init: RequestInit = {}, role?: Role): Promise<T> {
  const headers: Record<string, string> = {
    "X-Demo-Role": role || getRole(),
    ...((init.headers as Record<string, string>) || {}),
  };
  if (init.body && !(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(
      0,
      BASE
        ? `Could not reach the LandTrust Connect API at ${BASE}. If this is the hosted demo the API may be waking from sleep — the first request after an idle period takes up to a minute. Try again shortly.`
        : "Could not reach the LandTrust Connect API. Start the backend with `npm run dev` from the project root, or `uvicorn app.main:app --port 8000` from ./backend.",
    );
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string, role?: Role) => request<T>(path, {}, role),
  post: <T,>(path: string, body?: unknown, role?: Role) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }, role),
  upload: <T,>(path: string, form: FormData, role?: Role) =>
    request<T>(path, { method: "POST", body: form }, role),
};

/* ---------------------------------------------------------------- endpoints */

export const endpoints = {
  health: () => api.get<any>("/api/health"),
  roles: () => api.get<any>("/api/roles"),
  dashboard: () => api.get<any>("/api/dashboard"),

  properties: (query = "") => api.get<any>(`/api/properties${query}`),
  property: (id: string) => api.get<any>(`/api/properties/${id}`),
  documents: (id: string) => api.get<any>(`/api/properties/${id}/documents`),
  document: (id: string, docId: string) =>
    api.get<any>(`/api/properties/${id}/documents/${docId}`),
  claims: (id: string, query = "") => api.get<any>(`/api/properties/${id}/claims${query}`),
  claimEvidence: (id: string, claimId: string) =>
    api.get<any>(`/api/properties/${id}/claims/${claimId}/evidence`),
  contradictions: (id: string) => api.get<any>(`/api/properties/${id}/contradictions`),
  graph: (id: string) => api.get<any>(`/api/properties/${id}/graph`),
  risk: (id: string, history = false) =>
    api.get<any>(`/api/properties/${id}/risk${history ? "?history=true" : ""}`),
  resolution: (id: string) => api.get<any>(`/api/properties/${id}/resolution`),
  audit: (id: string) => api.get<any>(`/api/properties/${id}/audit`),
  profile: (id: string, role?: Role) => api.get<any>(`/api/properties/${id}/profile`, role),
  reassess: (id: string) => api.post<any>(`/api/properties/${id}/reassess`),

  documentModes: () => api.get<any>("/api/documents/modes"),
  uploadDocument: (form: FormData) => api.upload<any>("/api/documents/upload", form),
  documentFileUrl: (docId: string) => `${BASE}/api/documents/${docId}/file`,

  consentItems: () => api.get<any>("/api/consent/items"),
  consentList: (propertyId?: string) =>
    api.get<any>(`/api/consent${propertyId ? `?property_id=${propertyId}` : ""}`),
  requestConsent: (body: { property_id: string; items: string[]; purpose: string }) =>
    api.post<any>("/api/consent", body),
  decideConsent: (
    id: string,
    body: { approve: boolean; items?: string[]; time_limited?: boolean; note?: string },
  ) => api.post<any>(`/api/consent/${id}/decision`, body, "OWNER"),
  revokeConsent: (id: string) => api.post<any>(`/api/consent/${id}/revoke`, undefined, "OWNER"),

  messages: (propertyId: string) => api.get<any>(`/api/messages?property_id=${propertyId}`),
  sendMessage: (body: { property_id: string; body: string }, role?: Role) =>
    api.post<any>("/api/messages", body, role),

  assistantSuggestions: () => api.get<any>("/api/assistant/suggestions"),
  ask: (property_id: string, question: string) =>
    api.post<any>("/api/assistant/ask", { property_id, question }),
  assistantLog: (propertyId?: string) =>
    api.get<any>(`/api/assistant/log${propertyId ? `?property_id=${propertyId}` : ""}`),

  transactions: () => api.get<any>("/api/transactions"),
  stateReference: () => api.get<any>("/api/transactions/states"),
  attempt: (propertyId: string, action: string) =>
    api.post<any>(`/api/transactions/${propertyId}/attempt/${action}`),

  actionCatalogue: () => api.get<any>("/api/resolution/catalogue"),
  simulate: (property_id: string, action_keys: string[]) =>
    api.post<any>("/api/resolution/simulate", { property_id, action_keys }),
  applyAction: (property_id: string, action_key: string) =>
    api.post<any>("/api/resolution/apply", { property_id, action_key }, "OWNER"),

  scenarios: () => api.get<any>("/api/demo/scenarios"),
  resetDemo: () => api.post<any>("/api/demo/reset", undefined, "ADMIN"),
  presentation: () => api.get<any>("/api/demo/presentation"),

  metrics: () => api.get<any>("/api/research/metrics"),
  researchGap: () => api.get<any>("/api/research/gap"),
  architecture: () => api.get<any>("/api/research/architecture"),
  globalAudit: (query = "") => api.get<any>(`/api/audit${query}`),
};
