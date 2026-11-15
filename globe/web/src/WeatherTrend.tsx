import type { ShowcaseFrame } from "./showcase";
import { sparklinePoints, type DayWeather } from "./showcaseWeather";

const WIDTH = 64;
const HEIGHT = 16;

const ROWS = [
  { key: "rainMm", label: "Rain", color: "#7ee7ff", suffix: " mm", places: 1 },
  { key: "temperatureC", label: "Temp", color: "#f6c453", suffix: "°", places: 1 },
  { key: "soilMoisture", label: "Soil", color: "#86efac", suffix: "", places: 2 },
] as const;

function compact(value: number, places: number, suffix: string): string {
  const factor = 10 ** places;
  const rounded = Math.round(value * factor) / factor;
  return `${rounded.toFixed(places).replace(/\.?0+$/, "")}${suffix}`;
}

export function WeatherTrend({
  frames,
  weather,
  activeDate,
}: {
  frames: ShowcaseFrame[];
  weather: Record<string, DayWeather>;
  activeDate?: string | null;
}) {
  const ordered = [...frames].sort((a, b) => a.date.localeCompare(b.date));
  const rows = ROWS.map((row) => {
    const values = ordered.map((frame) => weather[frame.date]?.[row.key] ?? null);
    const points = sparklinePoints(values, WIDTH, HEIGHT);
    const last = [...values].reverse().find((value) => value != null);
    return { ...row, values, points, last };
  }).filter((row) => row.points.length > 0);
  if (!rows.length) return null;
  const summary = rows
    .map((row) => `${row.label} ends at ${row.last == null ? "no reading" : compact(row.last, row.places, row.suffix)}`)
    .join(". ");
  return (
    <div
      className="rounded-xl border border-white/10 bg-[#0c1522]/90 px-2 py-1"
      aria-label={`Weather trend across these radar dates. ${summary}. Open-Meteo.`}
    >
      {rows.map((row) => {
        const pieces: string[] = [];
        let run: string[] = [];
        let previous = -1;
        for (const point of row.points) {
          if (previous >= 0 && point.index !== previous + 1 && run.length) {
            pieces.push(run.join(" "));
            run = [];
          }
          run.push(`${point.x.toFixed(1)},${point.y.toFixed(1)}`);
          previous = point.index;
        }
        if (run.length) pieces.push(run.join(" "));
        const active = row.points.find((point) => ordered[point.index]?.date === activeDate);
        return (
          <div key={row.key} className="flex items-center gap-1.5" title={row.values.map((value) => (value == null ? "—" : compact(value, row.places, row.suffix))).join(", ")}>
            <span className="w-6 text-left text-[9px] text-slate-400">{row.label}</span>
            <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} aria-hidden="true">
              {pieces.map((points) => (
                <polyline key={points} points={points} fill="none" stroke={row.color} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" />
              ))}
              {active ? <circle cx={active.x} cy={active.y} r="2" fill={row.color} /> : null}
            </svg>
            <span className="min-w-8 text-right text-[9px] whitespace-nowrap text-slate-200">{row.last == null ? "—" : compact(row.last, row.places, row.suffix)}</span>
          </div>
        );
      })}
    </div>
  );
}
