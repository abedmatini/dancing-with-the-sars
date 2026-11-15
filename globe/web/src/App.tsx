import { useEffect, useMemo, useRef, useState } from "react";
import { fetchCatalog, fetchFlow, fetchGrid, fetchScene, readShowcase } from "./api";
import { DataNote } from "./DataNote";
import { MapKey } from "./MapKey";
import { Earth } from "./Earth";
import { Panel } from "./Panel";
import { ShowcaseRing } from "./ShowcaseRing";
import { loadShowcase, type ShowcaseFrame, type ShowcaseSpot } from "./showcase";
import { fetchShowcaseWeather, type DayWeather } from "./showcaseWeather";
import type { Catalog, FlowPath, RiskGrid, Scene, SourceMode } from "./types";
import { fetchWind, type WindField } from "./wind";

const DATA_NOTE_KEY = "sars-globe-nasa-note";

const TOUR = [
  { name: "Cape Town", lat: -33.9628, lon: 18.4098 },
  { name: "Los Angeles", lat: 34.045, lon: -118.525 },
  { name: "Attica", lat: 38.222, lon: 23.92 },
];

function readQuery(): { lat: number; lon: number; date: string | null } | null {
  const params = new URLSearchParams(window.location.search);
  const latRaw = params.get("lat");
  const lonRaw = params.get("lon");
  if (latRaw === null || lonRaw === null) return null;
  const lat = Number(latRaw);
  const lon = Number(lonRaw);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { lat, lon, date: params.get("date") };
}

function LayerButton({
  on,
  onClick,
  activeClass,
  children,
}: {
  on: boolean;
  onClick: () => void;
  activeClass: string;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      className={`rounded-full px-3 py-2 ${on ? activeClass : "bg-[#0c1522]/90"}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [offline, setOffline] = useState(false);
  const [bootError, setBootError] = useState("");
  const [scene, setScene] = useState<Scene | null>(null);
  const [grid, setGrid] = useState<RiskGrid | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [source, setSource] = useState<SourceMode>("mock");
  const [playing, setPlaying] = useState(false);
  const [spinning, setSpinning] = useState(true);
  const [basemap, setBasemap] = useState<"gibs" | "osm">("gibs");
  const [showDaily, setShowDaily] = useState(false);
  const [showFire, setShowFire] = useState(false);
  const [showSoil, setShowSoil] = useState(false);
  const [showSatellites, setShowSatellites] = useState(false);
  const [showWind, setShowWind] = useState(true);
  const [showRivers, setShowRivers] = useState(true);
  const [showRisk, setShowRisk] = useState(true);
  const [flow, setFlow] = useState<FlowPath | null>(null);
  const [wind, setWind] = useState<WindField | null>(null);
  const [busy, setBusy] = useState(false);
  const [approximate, setApproximate] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [flyKey, setFlyKey] = useState(0);
  const [zoomStep, setZoomStep] = useState(0);
  const [homeStep, setHomeStep] = useState(0);
  const [radarSpots, setRadarSpots] = useState<ShowcaseSpot[]>([]);
  const [radarOpenId, setRadarOpenId] = useState<string | null>(null);
  const [radarFly, setRadarFly] = useState(0);
  const [radarAnchor, setRadarAnchor] = useState<{ x: number; y: number } | null>(null);
  const [enlarged, setEnlarged] = useState<ShowcaseFrame | null>(null);
  const [reading, setReading] = useState("");
  const [readingBusy, setReadingBusy] = useState(false);
  const [radarWeather, setRadarWeather] = useState<Record<string, Record<string, DayWeather>>>({});
  const [radarWeatherReady, setRadarWeatherReady] = useState<Record<string, boolean>>({});
  const [focus, setFocus] = useState<{ lat: number; lon: number } | null>(null);
  const [tourLabel, setTourLabel] = useState("");
  const [dataNote, setDataNote] = useState(false);
  const request = useRef(0);
  const tourToken = useRef(0);

  const pins = useMemo(() => catalog?.groups.flatMap((group) => group.sites) ?? [], [catalog]);

  useEffect(() => {
    let cancelled = false;
    void loadShowcase().then((spots) => {
      if (cancelled) return;
      setRadarSpots(spots);
      for (const spot of spots) {
        void fetchShowcaseWeather(
          spot.id,
          spot.frames.map((frame) => frame.date),
        ).then((days) => {
          if (cancelled) return;
          setRadarWeather((current) => ({ ...current, [spot.id]: days }));
          setRadarWeatherReady((current) => ({ ...current, [spot.id]: true }));
        });
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    try {
      if (localStorage.getItem(DATA_NOTE_KEY) !== "seen") setDataNote(true);
    } catch {
      setDataNote(true);
    }
  }, []);

  function dismissDataNote() {
    setDataNote(false);
    try {
      localStorage.setItem(DATA_NOTE_KEY, "seen");
    } catch {
      /* The note can still be opened from the header. */
    }
  }

  useEffect(() => {
    if (!dataNote) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismissDataNote();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dataNote]);

  useEffect(() => {
    let cancelled = false;
    fetchCatalog()
      .then((result) => {
        if (cancelled) return;
        setCatalog(result.catalog);
        setOffline(result.offline);
        const query = readQuery();
        if (query) void openAt(query.lat, query.lon, query.date);
      })
      .catch((error: unknown) => {
        if (!cancelled) setBootError(error instanceof Error ? error.message : "The globe data could not load.");
      });
    return () => {
      cancelled = true;
    };
    // openAt is stable enough for the first query only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!playing || !scene) return;
    const timer = window.setInterval(() => {
      setDate((current) => {
        const dates = scene.dates;
        const index = Math.max(0, dates.indexOf(current ?? scene.date));
        return dates[(index + 1) % dates.length] ?? scene.date;
      });
    }, 1400);
    return () => window.clearInterval(timer);
  }, [playing, scene]);

  useEffect(() => {
    if (!scene || !date) return;
    const params = new URLSearchParams({
      lat: scene.lat.toFixed(4),
      lon: scene.lon.toFixed(4),
      date,
    });
    window.history.replaceState(null, "", `?${params}`);
  }, [scene, date]);

  useEffect(() => {
    if (!focus || !date) return;
    const token = request.current;
    fetchGrid(focus.lat, focus.lon, source, date)
      .then((next) => {
        if (token === request.current) setGrid(next);
      })
      .catch(() => {
        if (token === request.current) setGrid(null);
      });
  }, [focus, date, source]);

  useEffect(() => {
    if (!focus) return;
    let cancelled = false;
    setFlow(null);
    void fetchFlow(focus.lat, focus.lon).then((path) => {
      if (!cancelled) setFlow(path);
    });
    return () => {
      cancelled = true;
    };
  }, [focus]);

  useEffect(() => {
    if (!focus || !date) return;
    let cancelled = false;
    const box =
      scene && Math.abs(scene.lat - focus.lat) < 0.2 && Math.abs(scene.lon - focus.lon) < 0.2
        ? { west: scene.west, south: scene.south, east: scene.east, north: scene.north }
        : null;
    void fetchWind(focus.lat, focus.lon, date, box).then((field) => {
      if (!cancelled) setWind(field);
    });
    return () => {
      cancelled = true;
    };
  }, [focus, date, scene]);

  async function openAt(
    lat: number,
    lon: number,
    requestedDate: string | null,
    sourceOverride?: SourceMode,
  ) {
    const mode = sourceOverride ?? source;
    const token = ++request.current;
    setSpinning(false);
    setBusy(true);
    setFocus({ lat, lon });
    setFlyKey((value) => value + 1);
    setPanelOpen(true);
    try {
      const result = await fetchScene(lat, lon, mode, requestedDate);
      if (token !== request.current) return;
      setBootError("");
      setScene(result.scene);
      setOffline(result.offline);
      setApproximate(result.approximate);
      const nextDate =
        requestedDate && result.scene.dates.includes(requestedDate)
          ? requestedDate
          : result.scene.date;
      setDate(nextDate);
    } catch (error) {
      if (token === request.current) {
        setBootError(error instanceof Error ? error.message : "This location could not be loaded.");
        if (mode === "database") {
          setScene(null);
          setGrid(null);
          setPanelOpen(false);
        }
      }
    } finally {
      if (token === request.current) setBusy(false);
    }
  }

  async function runTour() {
    const token = ++tourToken.current;
    for (const stop of TOUR) {
      if (token !== tourToken.current) return;
      setTourLabel(stop.name);
      await openAt(stop.lat, stop.lon, null);
      await new Promise((resolve) => window.setTimeout(resolve, 4300));
    }
    if (token === tourToken.current) setTourLabel("");
  }

  const activeDate = date ?? scene?.date ?? "";

  return (
    <main className="relative h-full overflow-hidden bg-[#071018] text-slate-100">
      <Earth
        basemap={basemap}
        pins={pins}
        grid={grid}
        flow={showRivers ? flow : null}
        wind={showWind ? wind : null}
        showSatellites={showSatellites}
        showRisk={showRisk}
        target={focus ? { ...focus, key: flyKey } : null}
        spinning={spinning}
        showDaily={showDaily}
        showFire={showFire}
        showSoil={showSoil}
        onStopSpin={() => setSpinning(false)}
        zoomStep={zoomStep}
        homeStep={homeStep}
        onShowcase={(id) => {
          setSpinning(false);
          setEnlarged(null);
          setReading("");
          setRadarOpenId((current) => {
            if (current === id) return null;
            setRadarFly((value) => value + 1);
            return id;
          });
        }}
        radarSpots={radarSpots}
        radarSpot={radarSpots.find((spot) => spot.id === radarOpenId) ?? null}
        radarOpen={radarOpenId !== null}
        radarFly={radarFly}
        onRadarAnchor={setRadarAnchor}
        onPick={(lat, lon) => {
          tourToken.current += 1;
          setTourLabel("");
          setRadarOpenId(null);
          setEnlarged(null);
          void openAt(lat, lon, null);
        }}
      />
      {radarSpots.find((spot) => spot.id === radarOpenId) ? (
        <ShowcaseRing
          spot={radarSpots.find((spot) => spot.id === radarOpenId) as ShowcaseSpot}
          anchor={radarAnchor}
          enlarged={enlarged}
          reading={reading}
          readingBusy={readingBusy}
          weather={radarOpenId ? radarWeather[radarOpenId] ?? {} : {}}
          weatherReady={radarOpenId ? radarWeatherReady[radarOpenId] === true : false}
          onEnlarge={setEnlarged}
          onCloseEnlarge={() => setEnlarged(null)}
          onClose={() => {
            setRadarOpenId(null);
            setEnlarged(null);
          }}
          onAsk={() => {
            const spot = radarSpots.find((item) => item.id === radarOpenId);
            if (!spot) return;
            setReadingBusy(true);
            void fetchShowcaseWeather(
              spot.id,
              spot.frames.map((frame) => frame.date),
            ).then((days) => {
              const rows = spot.frames.flatMap((frame) => {
                const day = days[frame.date];
                return day ? [day] : [];
              });
              return readShowcase(spot.id, rows);
            }).then((result) => {
              setReading(result.error ? result.error : result.answer);
              setReadingBusy(false);
            });
          }}
        />
      ) : null}
      <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-col gap-3 p-3 sm:p-4">
        <div className="pointer-events-auto flex flex-wrap items-center gap-2">
          <div className="rounded-2xl border border-white/10 bg-[#0c1522]/80 px-3 py-2 backdrop-blur">
            <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-200/80">Dancing with the SARs</p>
            <h1 className="text-base font-semibold sm:text-lg">Drought and runoff globe</h1>
          </div>
          <button
            type="button"
            onClick={() => void runTour()}
            className="rounded-full bg-cyan-300 px-3 py-2 text-sm font-medium text-slate-950"
          >
            Guided tour
          </button>
          <button
            type="button"
            onClick={() => setDataNote(true)}
            className="rounded-full bg-[#0c1522]/90 px-3 py-2 text-sm text-slate-100"
          >
            NASA data
          </button>
          <button
            type="button"
            onClick={() => setSpinning((value) => !value)}
            className="rounded-full bg-[#0c1522]/90 px-3 py-2 text-sm text-slate-100"
          >
            {spinning ? "Pause rotation" : "Rotate"}
          </button>
          <button
            type="button"
            onClick={() => {
              setSpinning(false);
              setZoomStep((value) => value + 1);
            }}
            className="rounded-full bg-[#0c1522]/90 px-3 py-2 text-sm text-slate-100"
          >
            Zoom in
          </button>
          <button
            type="button"
            onClick={() => {
              setSpinning(false);
              setZoomStep((value) => value - 1);
            }}
            className="rounded-full bg-[#0c1522]/90 px-3 py-2 text-sm text-slate-100"
          >
            Zoom out
          </button>
          <button
            type="button"
            onClick={() => {
              tourToken.current += 1;
              request.current += 1;
              setTourLabel("");
              setPlaying(false);
              setPanelOpen(false);
              setFocus(null);
              setGrid(null);
              setFlow(null);
              setWind(null);
              setHomeStep((value) => value + 1);
            }}
            className="rounded-full bg-[#0c1522]/90 px-3 py-2 text-sm text-slate-100"
          >
            Reset view
          </button>
          {tourLabel ? <span className="text-sm text-cyan-100">Flying to {tourLabel}</span> : null}
        </div>
        <div className="pointer-events-auto flex flex-wrap gap-2 text-xs">
          <select
            aria-label="Study site"
            className="rounded-full bg-[#0c1522]/90 px-3 py-2"
            value=""
            onChange={(event) => {
              const pin = pins.find((site) => site.id === event.target.value);
              if (!pin) return;
              tourToken.current += 1;
              void openAt(pin.lat, pin.lon, null);
            }}
          >
            <option value="">Jump to a site</option>
            {catalog?.groups.map((group) => (
              <optgroup key={group.name} label={group.name}>
                {group.sites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <button type="button" className="rounded-full bg-[#0c1522]/90 px-3 py-2" onClick={() => setBasemap(basemap === "gibs" ? "osm" : "gibs")}>
            {basemap === "gibs" ? "Blue Marble" : "OpenStreetMap"}
          </button>
          <LayerButton on={showDaily} activeClass="bg-sky-300 text-slate-950" onClick={() => setShowDaily((value) => !value)}>
            Clouds
          </LayerButton>
          <LayerButton on={showFire} activeClass="bg-orange-300 text-slate-950" onClick={() => setShowFire((value) => !value)}>
            Fires
          </LayerButton>
          <LayerButton on={showSoil} activeClass="bg-lime-300 text-slate-950" onClick={() => setShowSoil((value) => !value)}>
            Soil moisture
          </LayerButton>
          <LayerButton
            on={showSatellites}
            activeClass="bg-cyan-300 text-slate-950"
            onClick={() => {
              setSpinning(false);
              setShowSatellites((value) => !value);
            }}
          >
            Satellites
          </LayerButton>
          <LayerButton on={showWind} activeClass="bg-slate-100 text-slate-950" onClick={() => setShowWind((value) => !value)}>
            Wind
          </LayerButton>
          <LayerButton on={showRivers} activeClass="bg-sky-200 text-slate-950" onClick={() => setShowRivers((value) => !value)}>
            Rivers
          </LayerButton>
          <LayerButton on={showRisk} activeClass="bg-amber-200 text-slate-950" onClick={() => setShowRisk((value) => !value)}>
            Risk colors
          </LayerButton>
        </div>
        {showSatellites ? (
          <p className="pointer-events-auto max-w-xl text-xs text-slate-300">
            Illustrated orbits for Sentinel-1, Landsat, and NISAR. Not a live tracking feed.
          </p>
        ) : null}
        {offline ? (
          <p className="pointer-events-auto max-w-xl rounded-xl bg-amber-200/10 px-3 py-2 text-sm text-amber-50">
            The API is unreachable, so pins and charts are coming from the bundled demo.
          </p>
        ) : null}
        {bootError ? (
          <p className="pointer-events-auto max-w-xl rounded-xl bg-rose-400/15 px-3 py-2 text-sm">{bootError}</p>
        ) : null}
      </header>
      {dataNote ? (
        <DataNote onClose={dismissDataNote} />
      ) : (
        <div className={panelOpen ? "max-md:hidden" : undefined}>
          <MapKey wind={wind} />
        </div>
      )}
      {panelOpen && scene ? (
        <Panel
          scene={scene}
          date={activeDate}
          playing={playing}
          offline={offline}
          approximate={approximate}
          busy={busy}
          source={source}
          flow={flow}
          wind={wind}
          onDate={(next) => {
            setPlaying(false);
            setDate(next);
          }}
          onPlaying={setPlaying}
          onSource={(next) => {
            setSource(next);
            if (focus) void openAt(focus.lat, focus.lon, date, next);
          }}
          onClose={() => {
            setPanelOpen(false);
            setPlaying(false);
            tourToken.current += 1;
          }}
        />
      ) : null}
    </main>
  );
}
