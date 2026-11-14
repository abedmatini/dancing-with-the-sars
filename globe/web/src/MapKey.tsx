import type { WindField } from "./wind";
import { windStrength } from "./wind";

export function MapKey({ wind }: { wind: WindField | null }) {
  const strength = wind ? windStrength(wind.speed_kmh) : null;
  return (
    <aside className="pointer-events-none absolute bottom-4 left-3 z-10 w-[min(19rem,calc(100%-1.5rem))] rounded-2xl border border-white/10 bg-[#0c1522]/90 p-3 text-xs leading-relaxed text-slate-200 shadow-xl backdrop-blur sm:left-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/80">Map key</p>
      <ul className="mt-2 space-y-2">
        <li className="flex items-start gap-2">
          <span className="mt-0.5 flex shrink-0 gap-1" aria-hidden>
            <span className="h-3 w-3 rounded-sm bg-[hsl(108_85%_42%)]" />
            <span className="h-3 w-3 rounded-sm bg-[hsl(60_85%_48%)]" />
            <span className="h-3 w-3 rounded-sm bg-[hsl(8_85%_48%)]" />
          </span>
          <span>Risk colors: green is low, under 40. Gold is medium, 40 to 64. Red is high, 65 and up.</span>
        </li>
        <li className="flex items-start gap-2">
          <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-orange-500" aria-hidden />
          <span>Fires: one orange mark means MODIS saw a hot spot. It is not a yellow-to-red strength scale.</span>
        </li>
        <li className="flex items-start gap-2">
          <span className="mt-1 flex shrink-0 items-end gap-1" aria-hidden>
            <span className="block h-1.5 w-1.5 rounded-sm bg-slate-100" />
            <span className="block h-3 w-1.5 rounded-sm bg-slate-100" />
            <span className="block h-5 w-1.5 rounded-sm bg-slate-100" />
          </span>
          <span>
            Wind: the arrow points where the wind is going. A short arrow is under 12 km/h, a middle one is 12 to 38, and a long one is 39 or more.
            {strength ? ` Here it is ${Math.round(wind?.speed_kmh ?? 0)} km/h, ${strength.label}.` : ""}
          </span>
        </li>
        <li className="flex items-start gap-2">
          <span className="mt-1.5 h-1 w-6 shrink-0 rounded-full bg-[#9ad7ff]" aria-hidden />
          <span>Rivers: the blue line is where rain from this spot runs downstream.</span>
        </li>
      </ul>
      <p className="mt-2 text-slate-400">Click a pin, or anywhere on the Earth, to open a 5 km study box.</p>
    </aside>
  );
}
