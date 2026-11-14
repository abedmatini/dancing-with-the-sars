import { useState } from "react";

const EXAMPLES = [
  {
    id: "medium",
    label: "Medium",
    wetness: 0.55,
    slope: 28,
    burned: false,
    day: "20260601",
    note: "Wetness is in the middle and the slope is steep, so the box turns gold.",
  },
  {
    id: "low",
    label: "Dry day",
    wetness: 0.15,
    slope: 8,
    burned: false,
    day: "20260912",
    note: "A dry, gentle slope. Little water and little tilt, so the box stays green.",
  },
  {
    id: "high",
    label: "Burned slope",
    wetness: 0.8,
    slope: 36,
    burned: true,
    day: "20260120",
    note: "Wet ground on a steep burned slope. The burn adds the last share, so the box turns red. That burn flag is still the labeled stand-in, not a NASA field.",
  },
] as const;

function runoffScore(wetness: number, slopeDeg: number, burned: boolean): number {
  const slopeFactor = Math.min(1, Math.max(0, slopeDeg / 40));
  const wetnessFactor = Math.min(1, Math.max(0, wetness));
  return Math.round(100 * (0.5 * slopeFactor + 0.32 * wetnessFactor + (burned ? 0.18 : 0)));
}

function riskHue(score: number): number {
  const clamped = Math.min(100, Math.max(0, score)) / 100;
  return 128 - clamped * 128;
}

function riskClass(score: number): string {
  if (score >= 65) return "high";
  if (score >= 40) return "medium";
  return "low";
}

export function DataNote({ onClose }: { onClose: () => void }) {
  const [exampleId, setExampleId] = useState<(typeof EXAMPLES)[number]["id"]>("medium");
  const example = EXAMPLES.find((item) => item.id === exampleId) ?? EXAMPLES[0];
  const score = runoffScore(example.wetness, example.slope, example.burned);
  const hue = riskHue(score);
  const raw = example.burned
    ? `"GWETTOP": { "${example.day}": ${example.wetness.toFixed(2)} }\n"burned": true`
    : `"GWETTOP": { "${example.day}": ${example.wetness.toFixed(2)} }`;
  return (
    <aside
      role="dialog"
      aria-labelledby="nasa-data-title"
      className="pointer-events-auto absolute left-3 top-44 z-30 flex max-h-[min(36rem,calc(100%-12rem))] w-[min(24rem,calc(100%-1.5rem))] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0c1522]/95 text-slate-100 shadow-2xl backdrop-blur sm:left-4"
    >
      <div className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/80">From the satellite value</p>
          <h2 id="nasa-data-title" className="text-base font-semibold leading-tight">
            How NASA data becomes the colors
          </h2>
        </div>
        <button type="button" className="rounded-md px-2 py-1 text-sm text-slate-300 hover:bg-white/10" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="space-y-3 overflow-y-auto px-4 py-3 text-sm leading-relaxed text-slate-200">
        <p>
          A click asks NASA for one 5 km box. POWER returns a daily wetness number for that spot, MERRA-2 GWETTOP, from
          0 (dry) to 1 (wet). Rainfall against normal stays in the chart.
        </p>
        <p>
          An Earthdata login can swap in a NISAR soil-moisture scene. Clouds, fires, and the soil picture are separate
          NASA layers. Slope is Copernicus. The burn scar is still a labeled stand-in.
        </p>
        <div role="tablist" aria-label="Worked examples" className="flex gap-1">
          {EXAMPLES.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === example.id}
              onClick={() => setExampleId(item.id)}
              className={`rounded-full px-3 py-1 text-xs ${
                item.id === example.id ? "bg-cyan-300 text-slate-950" : "bg-white/5 text-slate-200"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">A raw day, shortened</p>
          <pre className="mt-1 overflow-x-auto rounded-lg bg-black/40 px-3 py-2 text-xs leading-relaxed text-cyan-100">{raw}</pre>
        </div>
        <div className="flex items-center gap-3">
          <span
            className="inline-block h-9 w-14 shrink-0 rounded-md border border-white/20"
            style={{ background: `hsl(${hue} 85% 50% / 0.9)` }}
            aria-hidden
          />
          <p>
            Wetness {example.wetness.toFixed(2)}, slope {example.slope}°, {example.burned ? "burned" : "no burn"}. Half
            slope, 32% wetness, 18% burn gives{" "}
            <span className="font-medium text-white">
              {score}, {riskClass(score)}
            </span>
            . {example.note}
          </p>
        </div>
        <p className="text-xs text-slate-400">NASA Earthdata in the study box loads the live series. Mock and Database use the same color rule.</p>
      </div>
    </aside>
  );
}
