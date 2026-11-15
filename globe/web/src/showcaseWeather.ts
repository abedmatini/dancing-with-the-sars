export type DayWeather = {
  date: string;
  rainMm: number | null;
  temperatureC: number | null;
  soilMoisture: number | null;
};

type StoredDay = {
  date?: string;
  rain_mm?: unknown;
  temperature_c?: unknown;
  soil_moisture?: unknown;
};

type StoredFile = {
  spots?: { id?: string; days?: StoredDay[] }[];
};

const DATE = /^\d{4}-\d{2}-\d{2}$/;

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Rain and soil line for a thumbnail. Temperature stays in the AI prompt. */
export function weatherCaption(day: DayWeather | undefined): string {
  if (!day) return "";
  const rain = day.rainMm == null ? "rain —" : `${trimNumber(day.rainMm, 1)} mm`;
  const soil = day.soilMoisture == null ? "soil —" : `soil ${trimNumber(day.soilMoisture, 2)}`;
  return `${rain} · ${soil}`;
}

function trimNumber(value: number, places: number): string {
  const factor = 10 ** places;
  const rounded = Math.round(value * factor) / factor;
  return rounded.toFixed(places).replace(/\.?0+$/, "");
}

export function daysFromStored(payload: unknown): Record<string, Record<string, DayWeather>> {
  const spots = (payload as StoredFile | null)?.spots;
  const bySpot: Record<string, Record<string, DayWeather>> = {};
  if (!Array.isArray(spots)) return bySpot;
  for (const spot of spots) {
    const id = typeof spot?.id === "string" ? spot.id : "";
    if (!id) continue;
    const days: Record<string, DayWeather> = {};
    for (const day of spot.days ?? []) {
      const date = typeof day?.date === "string" ? day.date : "";
      if (!DATE.test(date)) continue;
      days[date] = {
        date,
        rainMm: finite(day.rain_mm),
        temperatureC: finite(day.temperature_c),
        soilMoisture: finite(day.soil_moisture),
      };
    }
    bySpot[id] = days;
  }
  return bySpot;
}

let stored: Promise<Record<string, Record<string, DayWeather>>> | null = null;

function loadStored(): Promise<Record<string, Record<string, DayWeather>>> {
  stored ??= fetch("/showcase/weather.json")
    .then((response) => (response.ok ? response.json() : {}))
    .then((payload) => daysFromStored(payload))
    .catch(() => ({}));
  return stored;
}

/** Stored Open-Meteo readings for one pin. The demo does not call the weather API. */
export async function fetchShowcaseWeather(
  spotId: string,
  dates: string[],
): Promise<Record<string, DayWeather>> {
  const table = await loadStored();
  const days = table[spotId] ?? {};
  const wanted = new Set(dates.filter((date) => DATE.test(date)));
  const picked: Record<string, DayWeather> = {};
  for (const date of wanted) {
    const day = days[date];
    if (day) picked[date] = day;
  }
  return picked;
}
