export type DayWeather = {
  date: string;
  rainMm: number | null;
  temperatureC: number | null;
  soilMoisture: number | null;
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

export function parseArchiveDays(payload: unknown, wanted: ReadonlySet<string>): Record<string, DayWeather> {
  const daily = (payload as { daily?: Record<string, unknown> } | null)?.daily;
  if (!daily) return {};
  const time = Array.isArray(daily.time) ? daily.time : [];
  const rain = Array.isArray(daily.precipitation_sum) ? daily.precipitation_sum : [];
  const temperature = Array.isArray(daily.temperature_2m_mean) ? daily.temperature_2m_mean : [];
  const soil = Array.isArray(daily.soil_moisture_0_to_7cm_mean) ? daily.soil_moisture_0_to_7cm_mean : [];
  const days: Record<string, DayWeather> = {};
  time.forEach((value, index) => {
    const date = typeof value === "string" ? value : "";
    if (!wanted.has(date)) return;
    days[date] = {
      date,
      rainMm: finite(rain[index]),
      temperatureC: finite(temperature[index]),
      soilMoisture: finite(soil[index]),
    };
  });
  return days;
}

const cache = new Map<string, Promise<Record<string, DayWeather>>>();

/** Open-Meteo daily archive for one pin. No API key. Same host as the wind arrows. */
export function fetchShowcaseWeather(
  lat: number,
  lon: number,
  dates: string[],
): Promise<Record<string, DayWeather>> {
  const wanted = dates.filter((date) => DATE.test(date));
  if (!wanted.length || !Number.isFinite(lat) || !Number.isFinite(lon)) return Promise.resolve({});
  const start = [...wanted].sort()[0];
  const end = [...wanted].sort().at(-1) ?? start;
  const key = `${lat.toFixed(4)},${lon.toFixed(4)},${start},${end}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const job = loadArchive(lat, lon, start, end, new Set(wanted)).catch(() => ({}));
  cache.set(key, job);
  return job;
}

async function loadArchive(
  lat: number,
  lon: number,
  start: string,
  end: string,
  wanted: ReadonlySet<string>,
): Promise<Record<string, DayWeather>> {
  const url =
    "https://archive-api.open-meteo.com/v1/archive" +
    `?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}` +
    `&start_date=${start}&end_date=${end}` +
    "&daily=precipitation_sum,temperature_2m_mean,soil_moisture_0_to_7cm_mean" +
    "&timezone=auto";
  const response = await fetch(url);
  if (!response.ok) return {};
  return parseArchiveDays(await response.json(), wanted);
}
