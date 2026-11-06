// Thin client for the KOI FastAPI backend. All financial data comes from the backend;
// the frontend never fabricates or computes financial figures beyond display formatting.

export const API_BASE = process.env.NEXT_PUBLIC_KOI_API ?? "http://127.0.0.1:8000";

// Backend payloads are large, evolving JSON documents; they are typed loosely on purpose.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T = Json>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch {
    throw new ApiError(0, `Cannot reach the KOI backend at ${API_BASE}. Is it running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export type Mode = "beginner" | "intermediate" | "advanced";

export const api = {
  health: () => request("/api/health"),
  home: () => request("/api/home"),
  search: (q: string) => request(`/api/search?q=${encodeURIComponent(q)}`),
  market: () => request("/api/market/overview"),
  analyze: (s: string, force = false) => request(`/api/companies/${encodeURIComponent(s)}/analyze?force=${force}`, { method: "POST" }),
  status: (s: string) => request(`/api/companies/${encodeURIComponent(s)}/status`),
  analysis: (s: string) => request(`/api/companies/${encodeURIComponent(s)}/analysis`),
  report: (s: string, mode: Mode, llm = false) =>
    request(`/api/companies/${encodeURIComponent(s)}/report?mode=${mode}&llm_narrative=${llm}`),
  financials: (s: string, period: "annual" | "quarterly") =>
    request(`/api/companies/${encodeURIComponent(s)}/financials?period=${period}`),
  prices: (s: string, days = 1825) => request(`/api/companies/${encodeURIComponent(s)}/prices?days=${days}`),
  dcf: (s: string, params: Record<string, number>) =>
    request(`/api/companies/${encodeURIComponent(s)}/dcf`, { method: "POST", body: JSON.stringify(params) }),
  saveReport: (s: string, llm = false) =>
    request(`/api/companies/${encodeURIComponent(s)}/reports`, { method: "POST", body: JSON.stringify({ llm_narrative: llm }) }),
  reports: (symbol?: string) => request(`/api/reports${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ""}`),
  savedReport: (id: number | string, mode: Mode) => request(`/api/reports/${id}?mode=${mode}`),
  deleteReport: (id: number) => request(`/api/reports/${id}`, { method: "DELETE" }),
  compareReports: (a: number, b: number) => request(`/api/reports/compare?a=${a}&b=${b}`),
  watchlist: () => request("/api/watchlist"),
  watchAdd: (s: string) => request(`/api/watchlist/${encodeURIComponent(s)}`, { method: "POST" }),
  watchRemove: (s: string) => request(`/api/watchlist/${encodeURIComponent(s)}`, { method: "DELETE" }),
  sectors: () => request("/api/sectors"),
  sector: (k: string) => request(`/api/sectors/${encodeURIComponent(k)}`),
  sectorLoad: (k: string) => request(`/api/sectors/${encodeURIComponent(k)}/load`, { method: "POST" }),
  compare: (symbols: string[]) => request(`/api/compare?symbols=${symbols.map(encodeURIComponent).join(",")}`),
  methodology: () => request("/api/methodology"),
  sources: () => request("/api/sources"),
  exportUrl: (s: string, period: "annual" | "quarterly") =>
    `${API_BASE}/api/companies/${encodeURIComponent(s)}/export.csv?period=${period}`,
};
