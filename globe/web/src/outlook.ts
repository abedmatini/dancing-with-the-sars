import type { Scene } from "./types";

export type DrynessOutlook = {
  headline: string;
  detail: string;
  note: string;
};

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/** Read the loaded series forward one month. Not a climate model. */
export function drynessOutlook(scene: Scene): DrynessOutlook {
  const soil = scene.soil_moisture.map((row) => row.value);
  const recentRainRows = scene.rainfall.slice(-3);
  const recentRain = recentRainRows.length
    ? mean(recentRainRows.map((row) => row.percent_normal))
    : scene.percent_normal;
  const recentSoil = soil.slice(-3);
  const priorSoil = soil.slice(-6, -3);
  const recentMean = mean(recentSoil);
  const priorMean = priorSoil.length ? mean(priorSoil) : recentMean;
  const monthChange = recentMean - priorMean;
  const enough = soil.length >= 6 && recentRainRows.length > 0;

  let headline = "The recent month does not show this land turning dry.";
  if (!enough) {
    headline = "Not enough scenes yet to say if the next month turns dry.";
  } else if (recentRain < 80 && monthChange < -0.005) {
    headline = "Yes. This land looks likely to be dry next month.";
  } else if (recentRain < 75) {
    headline = "It is already dry, and the next month looks much the same.";
  } else if (monthChange < -0.01) {
    headline = "Soil moisture is falling, so the next month may come out dry.";
  }

  const direction = monthChange <= -0.005 ? "fell" : monthChange >= 0.005 ? "rose" : "held steady";
  const detail = enough
    ? `Rain over the last three months was ${Math.round(recentRain)}% of normal (${scene.climatology_name}). Soil moisture ${direction} from ${priorMean.toFixed(3)} to ${recentMean.toFixed(3)} ${scene.soil_unit} across the last month of 12-day scenes.`
    : "This spot needs the June–November scene series before the next month can be read.";

  const source = scene.using_mock
    ? "Read from the bundled demo, carried forward one month."
    : "Read from the series loaded for this spot, carried forward one month.";

  return {
    headline,
    detail,
    note: `${source} Not a climate forecast, and not advice to buy or walk away.`,
  };
}
