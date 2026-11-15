import type { ShowcaseFrame, ShowcaseSpot } from "./showcase";
import { weatherCaption, type DayWeather } from "./showcaseWeather";

const RADIUS = 138;

const SLOTS = [
  { x: 0, y: -1 },
  { x: 1, y: 0 },
  { x: 0, y: 1 },
  { x: -1, y: 0 },
  { x: 0.72, y: -0.72 },
  { x: -0.72, y: 0.72 },
];

export function ShowcaseRing({
  spot,
  anchor,
  enlarged,
  reading,
  readingBusy,
  weather,
  weatherReady,
  onEnlarge,
  onCloseEnlarge,
  onAsk,
  onClose,
}: {
  spot: ShowcaseSpot;
  anchor: { x: number; y: number } | null;
  enlarged: ShowcaseFrame | null;
  reading: string;
  readingBusy: boolean;
  weather: Record<string, DayWeather>;
  weatherReady: boolean;
  onEnlarge: (frame: ShowcaseFrame) => void;
  onCloseEnlarge: () => void;
  onAsk: () => void;
  onClose: () => void;
}) {
  return (
    <>
      {anchor ? (
        <div className="pointer-events-none absolute inset-0 z-20">
          {spot.frames.slice(0, SLOTS.length).map((frame, index) => {
            const slot = SLOTS[index];
            const length = Math.hypot(slot.x, slot.y) || 1;
            const left = anchor.x + (slot.x / length) * RADIUS;
            const top = anchor.y + (slot.y / length) * RADIUS;
            return (
              <button
                key={frame.date}
                type="button"
                className="pointer-events-auto absolute w-[104px] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-white/30 bg-[#071018] shadow-lg"
                style={{ left, top }}
                onClick={() => onEnlarge(frame)}
                aria-label={`Open the ${frame.label} radar picture`}
              >
                <img src={frame.src} alt="" className="h-[78px] w-full bg-[#071018] object-contain" />
                <span className="block truncate px-1.5 pt-1 text-[10px] text-slate-100">{frame.label}</span>
                <span className="block truncate px-1.5 pb-1 text-[9px] text-amber-100/90">
                  {weatherCaption(weather[frame.date]) || (weatherReady ? "weather unavailable" : "…")}
                </span>
              </button>
            );
          })}
          <div
            className="pointer-events-auto absolute flex -translate-x-1/2 flex-col items-center gap-2"
            style={{ left: anchor.x, top: anchor.y + RADIUS + 98 }}
          >
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-full bg-amber-300 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-60"
                onClick={onAsk}
                disabled={readingBusy}
              >
                {readingBusy ? "Reading…" : "AI"}
              </button>
              <button
                type="button"
                className="rounded-full bg-[#0c1522]/90 px-3 py-1.5 text-xs text-slate-100"
                onClick={onClose}
              >
                Close
              </button>
                </div>
                <p className="text-[10px] text-slate-400">Rain and soil moisture from Open-Meteo.</p>
                {reading ? (
              <p className="max-h-40 w-72 overflow-auto rounded-2xl border border-white/10 bg-[#0c1522]/95 p-3 text-left text-xs leading-relaxed text-slate-100 shadow-xl">
                {reading}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
      {enlarged ? (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#071018]/80 p-6" role="dialog" aria-label={enlarged.label}>
          <button type="button" className="absolute inset-0" aria-label="Close the large picture" onClick={onCloseEnlarge} />
          <figure className="relative z-10 max-w-3xl">
            <img src={enlarged.src} alt={`NISAR radar, ${enlarged.label}, ${spot.name}`} className="max-h-[70vh] w-auto rounded-2xl border border-white/20 shadow-2xl" />
            <figcaption className="mx-auto mt-2 max-w-md text-center text-sm text-slate-100">
              <div>
                {spot.name} · {enlarged.label}
              </div>
              <div>{weatherCaption(weather[enlarged.date])}</div>
              <div className="text-xs text-slate-300">
                NISAR radar picture, not a photograph. Rain and soil moisture from Open-Meteo.
              </div>
            </figcaption>
          </figure>
        </div>
      ) : null}
    </>
  );
}
