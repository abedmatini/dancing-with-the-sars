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

/** Points for a tiny trend line. Missing days keep their place on the date axis. */
export function sparklinePoints(
  values: readonly (number | null)[],
  width: number,
  height: number,
): { index: number; x: number; y: number }[] {
  const present = values.filter((value): value is number => value != null);
  if (!present.length || width <= 0 || height <= 0) return [];
  const min = Math.min(...present);
  const max = Math.max(...present);
  const span = max - min || 1;
  const pad = 1.5;
  const last = Math.max(values.length - 1, 1);
  return values.flatMap((value, index) => {
    if (value == null) return [];
    const x = values.length === 1 ? width / 2 : pad + (index / last) * (width - pad * 2);
    const y = pad + (1 - (value - min) / span) * (height - pad * 2);
    return [{ index, x, y }];
  });
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
