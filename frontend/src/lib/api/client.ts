const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type Params = Record<string, string | number | undefined | null>;

function readableDetail(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg; // FastAPI 422
  return `Request failed (HTTP ${status})`;
}

/** The only place the app calls fetch. Components use the query hooks, never this directly. */
export async function apiGet<T>(path: string, params?: Params, signal?: AbortSignal): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const qs = query.toString(); // not query.size: missing in Safari < 17
  const url = `${BASE}${path}${qs ? `?${qs}` : ""}`;
  let res: Response;
  try {
    res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "Can't reach the server. Check your connection.");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, readableDetail(body, res.status));
  return body as T;
}

/** Writes. The session is an httpOnly cookie the browser sends by itself (same origin); scripts never see it. */
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, readableDetail(data, res.status));
  return data as T;
}
