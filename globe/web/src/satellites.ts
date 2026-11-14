/** Illustrated low-earth orbits. Not a live tracking feed, and no API key. */

type Sample = { t: number; lon: number; lat: number; alt: number };

const EARTH_M = 6_378_137;
const SIDEREAL = 86_164;

function samples(options: {
  altitudeM: number;
  inclinationDeg: number;
  periodMin: number;
  raanDeg: number;
  phaseDeg: number;
  minutes: number;
  stepSec: number;
}): Sample[] {
  const inc = (options.inclinationDeg * Math.PI) / 180;
  const raan = (options.raanDeg * Math.PI) / 180;
  const phase = (options.phaseDeg * Math.PI) / 180;
  const period = options.periodMin * 60;
  const radius = EARTH_M + options.altitudeM;
  const out: Sample[] = [];
  for (let t = 0; t <= options.minutes * 60; t += options.stepSec) {
    const theta = phase + (2 * Math.PI * t) / period;
    const x = radius * Math.cos(theta);
    const y = radius * Math.sin(theta);
    const y1 = y * Math.cos(inc);
    const z1 = y * Math.sin(inc);
    const cosR = Math.cos(raan);
    const sinR = Math.sin(raan);
    const xEci = x * cosR - y1 * sinR;
    const yEci = x * sinR + y1 * cosR;
    const earth = (2 * Math.PI * t) / SIDEREAL;
    const cosE = Math.cos(earth);
    const sinE = Math.sin(earth);
    const xE = xEci * cosE + yEci * sinE;
    const yE = -xEci * sinE + yEci * cosE;
    out.push({
      t,
      lon: (Math.atan2(yE, xE) * 180) / Math.PI,
      lat: (Math.atan2(z1, Math.hypot(xE, yE)) * 180) / Math.PI,
      alt: options.altitudeM,
    });
  }
  return out;
}

function packet(id: string, name: string, color: number[], track: Sample[]) {
  const flat: number[] = [];
  for (const sample of track) {
    flat.push(sample.t, Number(sample.lon.toFixed(4)), Number(sample.lat.toFixed(4)), Math.round(sample.alt));
  }
  return {
    id,
    name,
    description: "Illustrated orbit. Not a live position.",
    availability: "2026-11-14T00:00:00Z/2026-11-14T04:00:00Z",
    label: {
      text: name,
      font: "14px sans-serif",
      fillColor: { rgba: [232, 246, 255, 255] },
      outlineColor: { rgba: [4, 16, 24, 255] },
      outlineWidth: 2,
      style: "FILL_AND_OUTLINE",
      pixelOffset: { cartesian2: [10, 0] },
      scale: 0.85,
    },
    point: {
      pixelSize: 9,
      color: { rgba: color },
      outlineColor: { rgba: [4, 16, 24, 255] },
      outlineWidth: 2,
    },
    path: {
      width: 2,
      leadTime: 0,
      trailTime: 4200,
      resolution: 90,
      material: { solidColor: { color: { rgba: [...color.slice(0, 3), 150] } } },
    },
    position: {
      epoch: "2026-11-14T00:00:00Z",
      cartographicDegrees: flat,
      interpolationAlgorithm: "LAGRANGE",
      interpolationDegree: 2,
    },
  };
}

export function satelliteCzml() {
  const common = { minutes: 240, stepSec: 120 };
  return [
    {
      id: "document",
      name: "Illustrated orbits",
      version: "1.0",
      clock: {
        interval: "2026-11-14T00:00:00Z/2026-11-14T04:00:00Z",
        currentTime: "2026-11-14T00:00:00Z",
        multiplier: 160,
        range: "LOOP_STOP",
        step: "SYSTEM_CLOCK_MULTIPLIER",
      },
    },
    packet(
      "sentinel-1",
      "Sentinel-1",
      [126, 231, 255, 255],
      samples({ altitudeM: 693_000, inclinationDeg: 98.2, periodMin: 98.6, raanDeg: 18, phaseDeg: 0, ...common }),
    ),
    packet(
      "landsat",
      "Landsat",
      [255, 196, 120, 255],
      samples({ altitudeM: 705_000, inclinationDeg: 98.2, periodMin: 99, raanDeg: 150, phaseDeg: 50, ...common }),
    ),
    packet(
      "nisar",
      "NISAR",
      [186, 230, 160, 255],
      samples({ altitudeM: 747_000, inclinationDeg: 98.4, periodMin: 100, raanDeg: 260, phaseDeg: 20, ...common }),
    ),
  ];
}
