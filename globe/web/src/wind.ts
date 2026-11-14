export type WindArrow = {
  lat: number;
  lon: number;
  speed_kmh: number;
  direction_deg: number;
};

export type WindField = {
  speed_kmh: number;
  direction_deg: number;
  label: string;
  as_of: string;
  arrows: WindArrow[];
  credit: string;
};

const COMPASS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"];

/** Arrow length for the map key. Light, moderate, and strong are speed bands, not a warning. */
export function windStrength(speed: number): { label: string; scale: number } {
  if (speed < 12) return { label: "light", scale: 0.7 };
  if (speed < 39) return { label: "moderate", scale: 1.05 };
  return { label: "strong", scale: 1.5 };
}

export function windPhrase(speed: number, direction: number): string {
  if (speed < 1) return "calm";
  const wrapped = ((direction % 360) + 360) % 360;
  const name = COMPASS[Math.round(wrapped / 45) % 8] ?? "north";
  return `${Math.round(speed)} km/h from the ${name}`;
}

type Box = { west: number; south: number; east: number; north: number };

function spots(lat: number, lon: number, box: Box | null) {
  const west = box?.west ?? lon - 0.04;
  const east = box?.east ?? lon + 0.04;
  const south = box?.south ?? lat - 0.03;
  const north = box?.north ?? lat + 0.03;
  const rows = [0, 1, 2].map((index) => south + ((north - south) * index) / 2);
  const cols = [0, 1, 2].map((index) => west + ((east - west) * index) / 2);
  const points: { lat: number; lon: number }[] = [];
  for (const row of rows) {
    for (const col of cols) points.push({ lat: row, lon: col });
  }
  return points;
}

function reading(row: {
  current?: { wind_speed_10m?: number; wind_direction_10m?: number; time?: string };
  daily?: { wind_speed_10m_max?: Array<number | null>; wind_direction_10m_dominant?: Array<number | null>; time?: string[] };
}): { speed: number; direction: number; asOf: string } | null {
  const current = row.current;
  if (current && typeof current.wind_speed_10m === "number" && typeof current.wind_direction_10m === "number") {
    return { speed: current.wind_speed_10m, direction: current.wind_direction_10m, asOf: current.time ?? "" };
  }
  const speed = row.daily?.wind_speed_10m_max?.[0];
  const direction = row.daily?.wind_direction_10m_dominant?.[0];
  if (typeof speed === "number" && typeof direction === "number") {
    return { speed, direction, asOf: row.daily?.time?.[0] ?? "" };
  }
  return null;
}

async function request(url: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("wind");
  return response.json() as Promise<unknown>;
}

const MAX_SPEED_KMH = 250;

/** Drop readings that cannot be a 10 m wind arrow, and wrap direction into 0–360. */
export function cleanArrows(arrows: WindArrow[]): WindArrow[] {
  const kept: WindArrow[] = [];
  for (const arrow of arrows) {
    if (!Number.isFinite(arrow.lat) || !Number.isFinite(arrow.lon)) continue;
    if (!Number.isFinite(arrow.speed_kmh) || arrow.speed_kmh < 0 || arrow.speed_kmh > MAX_SPEED_KMH) continue;
    if (!Number.isFinite(arrow.direction_deg)) continue;
    kept.push({
      ...arrow,
      direction_deg: ((arrow.direction_deg % 360) + 360) % 360,
    });
  }
  return kept;
}

function arrowsFrom(payload: unknown, points: { lat: number; lon: number }[]): WindArrow[] {
  const rows = Array.isArray(payload) ? payload : [payload];
  const arrows: WindArrow[] = [];
  rows.forEach((row, index) => {
    const spot = points[index];
    const value = reading(row as Parameters<typeof reading>[0]);
    if (!spot || !value) return;
    arrows.push({
      lat: spot.lat,
      lon: spot.lon,
      speed_kmh: value.speed,
      direction_deg: value.direction,
    });
  });
  return arrows;
}

/** Open-Meteo wind for the study box. No API key. */
export async function fetchWind(lat: number, lon: number, date: string, box: Box | null): Promise<WindField | null> {
  const points = spots(lat, lon, box);
  const latitude = points.map((point) => point.lat.toFixed(4)).join(",");
  const longitude = points.map((point) => point.lon.toFixed(4)).join(",");
  const today = new Date().toISOString().slice(0, 10);
  const archive =
    date <= today
      ? `https://archive-api.open-meteo.com/v1/archive?latitude=${latitude}&longitude=${longitude}&start_date=${date}&end_date=${date}&daily=wind_speed_10m_max,wind_direction_10m_dominant&wind_speed_unit=kmh&timezone=auto`
      : "";
  const forecast = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=kmh&timezone=auto`;
  try {
    let found: WindArrow[] = [];
    let asOf = date;
    if (archive) {
      found = cleanArrows(arrowsFrom(await request(archive), points));
      asOf = date;
    }
    if (!found.length) {
      found = cleanArrows(arrowsFrom(await request(forecast), points));
      asOf = "current";
    }
    if (!found.length) return null;
    const center = found.reduce((best, arrow) => {
      const score = (arrow.lat - lat) ** 2 + (arrow.lon - lon) ** 2;
      return score < best.score ? { score, arrow } : best;
    }, { score: Number.POSITIVE_INFINITY, arrow: found[0] }).arrow;
    return {
      speed_kmh: center.speed_kmh,
      direction_deg: center.direction_deg,
      label: asOf === "current" ? `now ${windPhrase(center.speed_kmh, center.direction_deg)}` : windPhrase(center.speed_kmh, center.direction_deg),
      as_of: asOf,
      arrows: found,
      credit: "Open-Meteo",
    };
  } catch {
    return null;
  }
}
