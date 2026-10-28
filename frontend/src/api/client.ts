import type { Analysis, Heatmap, LatLon, Place, TripInput } from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

// Heatmap only needs the corridor shape; thinning keeps the request body small.
export const MAX_HEATMAP_POINTS_PER_PATH = 1500;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** DRF errors are either {detail: "..."} or {field: ["msg", ...], ...}. */
export function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    const parts = Object.entries(record).map(([field, messages]) => {
      const text = Array.isArray(messages) ? messages.join(" ") : String(messages);
      return `${field.replace(/_/g, " ")}: ${text}`;
    });
    if (parts.length) return parts.join(" · ");
  }
  return `Request failed (${status}).`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(body, response.status), response.status);
  return body as T;
}

export function thinPath(path: LatLon[], maxPoints = MAX_HEATMAP_POINTS_PER_PATH): LatLon[] {
  if (path.length <= maxPoints) return path;
  const stride = Math.ceil(path.length / maxPoints);
  const thinned = path.filter((_, i) => i % stride === 0);
  const last = path[path.length - 1]!;
  if (thinned[thinned.length - 1] !== last) thinned.push(last);
  return thinned;
}

export const api = {
  analyze: (trip: TripInput, signal?: AbortSignal) =>
    request<Analysis>("/api/analyze/", { method: "POST", body: JSON.stringify(trip), signal }),

  heatmap: (paths: LatLon[][], start: string, loadLb: number, signal?: AbortSignal) =>
    request<Heatmap>("/api/heatmap/", {
      method: "POST",
      body: JSON.stringify({ paths: paths.map((p) => thinPath(p)), start, load_lb: loadLb }),
      signal,
    }),

  geocode: (query: string, signal?: AbortSignal) =>
    request<{ results: Place[] }>(`/api/geocode/?q=${encodeURIComponent(query)}`, { signal }).then(
      (body) => body.results,
    ),
};
