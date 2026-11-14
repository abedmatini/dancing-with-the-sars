import { motion } from "framer-motion";
import { useEffect, useState, type FormEvent } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchChat, fetchSummary } from "./api";
import type { ChatTurn, Scene, SourceMode } from "./types";

const chartTip = {
  contentStyle: {
    background: "#0e1724",
    border: "1px solid #243246",
    borderRadius: 8,
    color: "#e7eef7",
  },
};

function badgeTone(label: string): string {
  return label.startsWith("LIVE")
    ? "bg-emerald-400/15 text-emerald-200"
    : "bg-amber-300/15 text-amber-100";
}

export function Panel({
  scene,
  date,
  playing,
  offline,
  approximate,
  busy,
  source,
  onDate,
  onPlaying,
  onSource,
  onClose,
}: {
  scene: Scene;
  date: string;
  playing: boolean;
  offline: boolean;
  approximate: boolean;
  busy: boolean;
  source: SourceMode;
  onDate: (date: string) => void;
  onPlaying: (playing: boolean) => void;
  onSource: (source: SourceMode) => void;
  onClose: () => void;
}) {
  const [summary, setSummary] = useState("");
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [asking, setAsking] = useState(false);
  const index = Math.max(0, scene.dates.indexOf(date));
  const risk = scene.risk_series.find((row) => row.date === date) ?? scene.risk;
  const soil = scene.soil_moisture.find((row) => row.date === date);

  useEffect(() => {
    setSummary("");
    setSummaryError(null);
    setTurns([]);
  }, [scene.id, scene.source]);

  async function summarize() {
    setSummarizing(true);
    const result = await fetchSummary(scene.lat, scene.lon, scene.source, date);
    setSummary(result.text);
    setSummaryError(result.error);
    setSummarizing(false);
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || asking) return;
    setQuestion("");
    setTurns((current) => [...current, { role: "user", text }]);
    setAsking(true);
    const result = await fetchChat(scene.lat, scene.lon, scene.source, date, text);
    const answer = result.error ? `${result.error} ${result.answer}` : result.answer;
    setTurns((current) => [...current, { role: "assistant", text: answer }]);
    setAsking(false);
  }

  const rain = scene.rainfall.map((row) => ({
    month: row.time.slice(0, 7),
    observed: row.observed_mm,
    normal: row.climatology_mm,
  }));

  return (
    <motion.aside
      initial={{ x: 28, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 280, damping: 30 }}
      className="fixed inset-x-0 bottom-0 z-20 flex max-h-[72vh] flex-col overflow-hidden rounded-t-2xl border border-white/10 bg-[#0c1522]/95 text-slate-100 shadow-2xl backdrop-blur md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-[400px] md:rounded-none md:border-y-0 md:border-r-0"
    >
      <div className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/80">5 km study box</p>
          <h2 className="text-lg font-semibold leading-tight">{scene.name}</h2>
          <p className="text-sm text-slate-400">{scene.coordinates}</p>
        </div>
        <button type="button" className="rounded-md px-2 py-1 text-slate-300 hover:bg-white/10" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="space-y-4 overflow-y-auto px-4 py-4">
        <p className="text-sm text-slate-300">{scene.description}</p>
        {scene.terrain ? <p className="text-xs text-slate-400">{scene.terrain}</p> : null}
        {approximate ? (
          <p className="rounded-lg bg-amber-300/10 px-3 py-2 text-sm text-amber-100">
            The API is offline, so this is the nearest bundled preset rather than an exact click.
          </p>
        ) : null}
        {offline ? (
          <p className="text-xs text-slate-400">Bundled demo. Live NASA calls need the globe API.</p>
        ) : null}
        <div className="flex gap-2">
          {(["mock", "earthdata"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => onSource(mode)}
              className={`rounded-full px-3 py-1 text-xs ${
                source === mode ? "bg-cyan-300 text-slate-950" : "bg-white/5 text-slate-200"
              }`}
            >
              {mode === "mock" ? "Mock" : "NASA Earthdata"}
            </button>
          ))}
          {busy ? <span className="self-center text-xs text-slate-400">Loading…</span> : null}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(scene.layers).map(([key, label]) => (
            <span key={key} className={`rounded-full px-2 py-1 text-[11px] ${badgeTone(label)}`}>
              {label}
            </span>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Metric label="Rainfall vs normal" value={`${scene.percent_normal.toFixed(0)}%`} detail={scene.rainfall_month} />
          <Metric
            label="Soil moisture"
            value={soil ? soil.value.toFixed(3) : scene.soil_value.toFixed(3)}
            detail={scene.soil_unit}
          />
          <Metric label="Runoff class" value={risk.class} detail={`${risk.score.toFixed(0)} / 100`} />
          <Metric label="Burned share" value={`${scene.burned_percent.toFixed(1)}%`} detail="of the grid" />
          <Metric label="Mean slope" value={`${scene.slope.mean.toFixed(1)}°`} detail={`${scene.slope.min.toFixed(0)}–${scene.slope.max.toFixed(0)}°`} />
        </div>
        <p className="text-xs text-slate-400">{scene.risk.ranges}</p>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-medium">12-day scenes</p>
            <button
              type="button"
              className="rounded-full bg-white/10 px-3 py-1 text-xs"
              onClick={() => onPlaying(!playing)}
            >
              {playing ? "Pause" : "Play"}
            </button>
          </div>
          <input
            aria-label="Scene date"
            type="range"
            min={0}
            max={Math.max(0, scene.dates.length - 1)}
            value={index}
            onChange={(event) => onDate(scene.dates[Number(event.target.value)] ?? date)}
            className="w-full accent-cyan-300"
          />
          <p className="mt-1 text-xs text-slate-400">{date}</p>
        </div>
        <div className="h-36">
          <p className="mb-1 text-xs text-slate-400">Soil moisture</p>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={scene.soil_moisture}>
              <CartesianGrid stroke="#243246" vertical={false} />
              <XAxis dataKey="date" hide />
              <YAxis stroke="#93a4b8" width={36} tick={{ fontSize: 10 }} />
              <Tooltip {...chartTip} />
              <Line type="monotone" dataKey="value" stroke="#67e8f9" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="h-40">
          <p className="mb-1 text-xs text-slate-400">Rainfall against {scene.climatology_name}</p>
          <ResponsiveContainer width="100%" height="85%">
            <BarChart data={rain}>
              <CartesianGrid stroke="#243246" vertical={false} />
              <XAxis dataKey="month" stroke="#93a4b8" tick={{ fontSize: 10 }} />
              <YAxis stroke="#93a4b8" width={32} tick={{ fontSize: 10 }} />
              <Tooltip {...chartTip} />
              <Bar dataKey="normal" fill="#475569" radius={2} />
              <Bar dataKey="observed" fill="#38bdf8" radius={2} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => void summarize()}
            className="rounded-lg bg-cyan-300 px-3 py-2 text-sm font-medium text-slate-950"
          >
            {summarizing ? "Summarizing…" : "Summarize"}
          </button>
          {summaryError ? <p className="text-sm text-amber-100">{summaryError}</p> : null}
          {summary ? <p className="text-sm leading-relaxed text-slate-200">{summary}</p> : null}
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Ask</p>
          <div className="mb-2 space-y-2">
            {turns.map((turn, turnIndex) => (
              <p
                key={`${turn.role}-${turnIndex}`}
                className={turn.role === "user" ? "text-sm text-cyan-100" : "text-sm text-slate-300"}
              >
                {turn.text}
              </p>
            ))}
            {asking ? <p className="text-xs text-slate-400">Looking at the numbers on this page…</p> : null}
          </div>
          <form onSubmit={(event) => void ask(event)} className="flex gap-2">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="How does rainfall compare with normal?"
              className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none"
            />
            <button type="submit" className="rounded-lg bg-white/10 px-3 text-sm">
              Send
            </button>
          </form>
        </div>
        {scene.notice ? <p className="text-xs text-slate-400">{scene.notice}</p> : null}
      </div>
    </motion.aside>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className="text-lg font-semibold leading-tight">{value}</p>
      <p className="text-[11px] text-slate-500">{detail}</p>
    </div>
  );
}
