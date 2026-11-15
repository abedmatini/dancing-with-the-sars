import type { Catalog, DemoFile, FlowPath, RiskGrid, Scene, SourceMode } from "./types";

const configured = import.meta.env.VITE_API_BASE;
const fallback = import.meta.env.PROD
  ? "https://sars-globe-api.onrender.com"
  : "http://127.0.0.1:8091";
const API_BASE = (configured === undefined || configured === "" ? fallback : configured).replace(/\/$/, "");

let demoPromise: Promise<DemoFile> | null = null;
let apiUp: boolean | null = null;

function loadDemo(): Promise<DemoFile> {
  demoPromise ??= fetch("/demo.json").then((response) => {
    if (!response.ok) throw new Error("The bundled demo could not be loaded.");
    return response.json() as Promise<DemoFile>;
  });
  return demoPromise;
}

export async function apiReachable(): Promise<boolean> {
  if (apiUp !== null) return apiUp;
  try {
    const response = await fetch(`${API_BASE}/health`, {
      signal: AbortSignal.timeout(75_000),
    });
    apiUp = response.ok;
  } catch {
    apiUp = false;
  }
  return apiUp;
}

async function fetchOk(url: string, init?: RequestInit): Promise<Response | null> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(url, init);
      if (response.ok) return response;
    } catch {
      // A free Render instance can drop the first call while it wakes.
    }
  }
  return null;
}

export async function fetchCatalog(): Promise<{ catalog: Catalog; offline: boolean }> {
  if (await apiReachable()) {
    const response = await fetchOk(`${API_BASE}/sites`);
    if (response) return { catalog: (await response.json()) as Catalog, offline: false };
  }
  const demo = await loadDemo();
  return { catalog: demo.sites, offline: true };
}

function nearestDemo(demo: DemoFile, lat: number, lon: number) {
  let bestId = "";
  let best = Number.POSITIVE_INFINITY;
  for (const [id, entry] of Object.entries(demo.scenes)) {
    const distance = (entry.scene.lat - lat) ** 2 + (entry.scene.lon - lon) ** 2;
    if (distance < best) {
      best = distance;
      bestId = id;
    }
  }
  return demo.scenes[bestId];
}

function withDate(scene: Scene, date: string | null): Scene {
  if (!date || !scene.risk_series.some((row) => row.date === date)) return scene;
  const risk = scene.risk_series.find((row) => row.date === date);
  const soil = scene.soil_moisture.find((row) => row.date === date);
  return {
    ...scene,
    date,
    risk: risk ? { ...scene.risk, score: risk.score, class: risk.class } : scene.risk,
    soil_value: soil ? soil.value : scene.soil_value,
  };
}

async function storedError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string" && body.detail) return body.detail;
  } catch {
    /* The status is enough. */
  }
  return "Nothing is stored for this place.";
}

export async function fetchScene(
  lat: number,
  lon: number,
  source: SourceMode,
  date: string | null,
): Promise<{ scene: Scene; offline: boolean; approximate: boolean }> {
  if (source === "database") {
    if (!(await apiReachable())) {
      throw new Error("Stored readings need the globe API. This button does not use the bundled demo.");
    }
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon), source });
    if (date) params.set("date", date);
    const response = await fetch(`${API_BASE}/site?${params}`);
    if (response.status === 404) throw new Error(await storedError(response));
    if (!response.ok) throw new Error("The stored readings could not be loaded.");
    return { scene: (await response.json()) as Scene, offline: false, approximate: false };
  }
  if (await apiReachable()) {
    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lon),
      source,
    });
    if (date) params.set("date", date);
    const response = await fetchOk(`${API_BASE}/site?${params}`);
    if (response) {
      return { scene: (await response.json()) as Scene, offline: false, approximate: false };
    }
  }
  const demo = await loadDemo();
  const entry = nearestDemo(demo, lat, lon);
  const approximate =
    Math.abs(entry.scene.lat - lat) > 0.05 || Math.abs(entry.scene.lon - lon) > 0.05;
  return { scene: withDate(entry.scene, date), offline: true, approximate };
}

export async function fetchGrid(
  lat: number,
  lon: number,
  source: SourceMode,
  date: string | null,
): Promise<RiskGrid | null> {
  if (source === "database") {
    if (!(await apiReachable())) return null;
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon), source });
    if (date) params.set("date", date);
    const response = await fetch(`${API_BASE}/risk-grid?${params}`);
    if (!response.ok) return null;
    return (await response.json()) as RiskGrid;
  }
  if (await apiReachable()) {
    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lon),
      source,
    });
    if (date) params.set("date", date);
    const response = await fetchOk(`${API_BASE}/risk-grid?${params}`);
    if (response) return (await response.json()) as RiskGrid;
  }
  const demo = await loadDemo();
  const entry = nearestDemo(demo, lat, lon);
  if (!entry) return null;
  if (date && entry.grids[date]) return entry.grids[date];
  const dates = Object.keys(entry.grids);
  return entry.grids[dates[dates.length - 1]] ?? null;
}

function cleanRiverName(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const name = value.trim();
  if (!name || name.toLowerCase() === "unknown" || name.toLowerCase() === "null") return null;
  return name;
}

function simplifyPath(coordinates: [number, number][]): [number, number][] {
  if (coordinates.length < 3) return coordinates;
  const kept: [number, number][] = [coordinates[0]];
  for (const point of coordinates.slice(1)) {
    const last = kept[kept.length - 1];
    const north = (point[1] - last[1]) * 110.54;
    const east = (point[0] - last[0]) * 111.32 * Math.cos((((point[1] + last[1]) / 2) * Math.PI) / 180);
    if (Math.hypot(east, north) >= 1.2) kept.push(point);
  }
  const end = coordinates[coordinates.length - 1];
  if (kept[kept.length - 1][0] !== end[0] || kept[kept.length - 1][1] !== end[1]) kept.push(end);
  if (kept.length <= 420) return kept;
  const stride = Math.ceil(kept.length / 420);
  const trimmed = kept.filter((_, index) => index % stride === 0);
  trimmed.push(end);
  return trimmed;
}

function pathFromMerit(payload: unknown): FlowPath | null {
  const features = (payload as { value?: { features?: Array<{ properties?: Record<string, unknown>; geometry?: { coordinates?: number[][] } }> } })
    ?.value?.features;
  if (!features?.length) return null;
  const coordinates: [number, number][] = [];
  const rivers: FlowPath["rivers"] = [];
  const seen = new Set<string>();
  for (const feature of features) {
    const coords = feature.geometry?.coordinates ?? [];
    for (const pair of coords) {
      if (pair.length >= 2 && Number.isFinite(pair[0]) && Number.isFinite(pair[1])) {
        coordinates.push([pair[0], pair[1]]);
      }
    }
    const name = cleanRiverName(feature.properties?.gnis_name) ?? cleanRiverName(feature.properties?.nameid);
    if (name && !seen.has(name) && coords.length) {
      seen.add(name);
      const mid = coords[Math.floor(coords.length / 2)] ?? coords[0];
      rivers.push({ name, lon: mid[0], lat: mid[1] });
    }
  }
  if (coordinates.length < 2) return null;
  const simplified = simplifyPath(coordinates);
  let length = 0;
  for (let index = 1; index < simplified.length; index += 1) {
    const start = simplified[index - 1];
    const end = simplified[index];
    const north = (end[1] - start[1]) * 110.54;
    const east = (end[0] - start[0]) * 111.32 * Math.cos((((end[1] + start[1]) / 2) * Math.PI) / 180);
    length += Math.hypot(east, north);
  }
  const summary = rivers.length
    ? `Rain from this spot runs downstream through ${rivers
        .slice(0, 4)
        .map((river) => river.name)
        .join(", ")}.`
    : length < 2
      ? "This spot is already near the downstream end, so the blue path is short and this stretch has no named river."
      : "Rain from this spot has a downstream path. This stretch has no named river in the global river map.";
  return { coordinates: simplified, rivers: rivers.slice(0, 6), summary, credit: "MERIT-Basins" };
}

/** Prefer the globe API, which adds OpenStreetMap names. Fall back to MERIT directly. */
export async function fetchFlow(lat: number, lon: number): Promise<FlowPath | null> {
  if (await apiReachable()) {
    const response = await fetchOk(`${API_BASE}/flow?lat=${encodeURIComponent(String(lat))}&lon=${encodeURIComponent(String(lon))}`);
    if (response) return (await response.json()) as FlowPath;
  }
  try {
    const response = await fetch(
      `https://merit.internetofwater.app/processes/river-runner/execution?lat=${encodeURIComponent(String(lat))}&lng=${encodeURIComponent(String(lon))}`,
    );
    if (!response.ok) return null;
    return pathFromMerit(await response.json());
  } catch {
    return null;
  }
}

export async function fetchSummary(
  lat: number,
  lon: number,
  source: SourceMode,
  date: string,
): Promise<{ text: string; error: string | null }> {
  if (await apiReachable()) {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon), source, date });
    const response = await fetchOk(`${API_BASE}/summary?${params}`);
    if (response) {
      return (await response.json()) as { text: string; error: string | null };
    }
  }
  return {
    text: "The summary service is offline. The charts on this page still use the bundled demo.",
    error: null,
  };
}

export async function fetchPodcast(
  lat: number,
  lon: number,
  source: SourceMode,
  date: string,
): Promise<{ text: string; error: string | null } | null> {
  if (!(await apiReachable())) return null;
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon), source, date });
  const response = await fetchOk(`${API_BASE}/podcast?${params}`);
  if (!response) return null;
  return (await response.json()) as { text: string; error: string | null };
}

export async function readShowcase(
  id: string,
  weather: { date: string; rainMm: number | null; temperatureC: number | null; soilMoisture: number | null }[] = [],
): Promise<{ answer: string; provider: string; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE}/showcase/read`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id,
        weather: weather.map((day) => ({
          date: day.date,
          rain_mm: day.rainMm,
          temperature_c: day.temperatureC,
          soil_moisture: day.soilMoisture,
        })),
      }),
    });
    if (!response.ok) {
      return {
        answer: "The radar pictures could not be sent.",
        provider: "none",
        error: `HTTP ${response.status}`,
      };
    }
    return (await response.json()) as { answer: string; provider: string; error: string | null };
  } catch {
    return {
      answer: "The globe API is not running, so Claude was not asked to read these pictures.",
      provider: "none",
      error: "unreachable",
    };
  }
}

export async function fetchChat(
  lat: number,
  lon: number,
  source: SourceMode,
  date: string,
  question: string,
): Promise<{ answer: string; error: string | null }> {
  if (await apiReachable()) {
    const response = await fetchOk(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lat, lon, source, date, question }),
    });
    if (response) {
      return (await response.json()) as { answer: string; error: string | null };
    }
  }
  return {
    answer:
      "The API is not reachable, so this copy cannot answer from the live numbers. Start the globe API, or read the metric cards in the panel.",
    error: null,
  };
}
