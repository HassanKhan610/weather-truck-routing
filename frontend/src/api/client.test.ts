import { api, ApiError, errorMessage, normalizeBaseUrl, thinPath } from "./client";
import type { LatLon } from "./types";

describe("errorMessage", () => {
  it("prefers detail", () => {
    expect(errorMessage({ detail: "Route not found" }, 422)).toBe("Route not found");
  });

  it("joins field errors", () => {
    expect(errorMessage({ load_lb: ["Too big."], origin: ["Required."] }, 400)).toBe(
      "load lb: Too big. · origin: Required.",
    );
  });

  it("falls back to the status", () => {
    expect(errorMessage(null, 500)).toBe("Request failed (500).");
  });
});

describe("thinPath", () => {
  it("keeps short paths and always keeps both ends", () => {
    const path: LatLon[] = Array.from({ length: 10 }, (_, i) => [i, i]);
    expect(thinPath(path, 20)).toBe(path);
    const thinned = thinPath(path, 4);
    expect(thinned[0]).toEqual([0, 0]);
    expect(thinned.at(-1)).toEqual([9, 9]);
    expect(thinned.length).toBeLessThanOrEqual(5);
  });
});

describe("api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("throws ApiError with the server message", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify({ detail: "No route" }), { status: 422 })),
    );
    await expect(api.geocode("Dallas")).rejects.toEqual(new ApiError("No route", 422));
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.geocode("Dallas")).rejects.toMatchObject({ status: 0 });
  });

  it("sends thinned paths to the heatmap endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const long: LatLon[] = Array.from({ length: 4000 }, (_, i) => [30 + i / 1000, -90]);
    await api.heatmap([long], "2026-11-02T06:00:00Z", 1000);
    const body = JSON.parse(fetchMock.mock.calls[0]![1].body);
    expect(body.paths[0].length).toBeLessThanOrEqual(1501);
    expect(body.load_lb).toBe(1000);
  });
});

describe("normalizeBaseUrl", () => {
  it.each([
    [undefined, "http://localhost:8000"],
    ["", "http://localhost:8000"],
    ["api.example.vercel.app", "https://api.example.vercel.app"],
    ["https://api.example.vercel.app/", "https://api.example.vercel.app"],
    [" http://localhost:8000 ", "http://localhost:8000"],
  ])("%s -> %s", (raw, expected) => {
    expect(normalizeBaseUrl(raw)).toBe(expected);
  });
});
