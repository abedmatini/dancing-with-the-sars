import type { Catalog, DemoFile, RiskGrid, Scene, SourceMode } from "./types";

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
  const scene = withDate(entry.scene, date);
  return {
    scene: {
      ...scene,
      soil_available: false,
      soil_note: "Data unavailable",
      soil_moisture: [],
      soil_value: 0,
      soil_unit: "",
    },
    offline: true,
    approximate,
  };
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
