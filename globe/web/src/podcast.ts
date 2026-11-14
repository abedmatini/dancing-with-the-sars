import type { Scene } from "./types";

export function sceneCadence(dates: string[]): string {
  if (dates.length < 2) return "Scenes";
  const gaps = dates.slice(1).map((day, index) => {
    const previous = Date.parse(dates[index] ?? day);
    return (Date.parse(day) - previous) / 86_400_000;
  });
  const sorted = [...gaps].sort((left, right) => left - right);
  const median = sorted[Math.floor(sorted.length / 2)] ?? 12;
  if (median <= 2) return "Daily scenes";
  if (median <= 6) return "Scenes every few days";
  return "12-day scenes";
}

/** About 30 seconds when read aloud. Uses only numbers already on the scene. */
export function briefingScript(scene: Scene, date: string): string {
  const soil = scene.soil_moisture.map((row) => row.value);
  const first = soil[0] ?? scene.soil_value;
  const selected = scene.soil_moisture.find((row) => row.date === date)?.value ?? soil[soil.length - 1] ?? scene.soil_value;
  const risk = scene.risk_series.find((row) => row.date === date) ?? scene.risk;
  const trend =
    selected > first + 0.01 ? "higher than the first scene" : selected < first - 0.01 ? "lower than the first scene" : "about the same as the first scene";
  const source = scene.using_mock
    ? "These numbers are the seeded demo, not a live satellite download."
    : "Rainfall and soil wetness are NASA POWER values, slope is Copernicus, and the burn mask is still a seeded layer.";
  return (
    `Briefing for ${scene.name} on ${date}. ` +
    `Rain is ${Math.round(scene.percent_normal)} percent of normal. Soil moisture is ${trend}. ` +
    `Runoff is ${risk.class}, ${Math.round(risk.score)} out of 100. ` +
    `Burned share is ${Math.round(scene.burned_percent)} percent. Mean slope is ${Math.round(scene.slope.mean)} degrees. ` +
    "A land buyer uses this to judge whether the ground is drying. " +
    "A grower uses the rain and soil to plan water. " +
    "A fire crew pairs burned share with slope, because steep burned ground sheds sediment after rain. " +
    "An insurer treats the class as today's flag, not a promise. " +
    `${source} This reading is not a climate forecast and not advice to buy or walk away.`
  );
}

export function speakBriefing(text: string): void {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 1;
  window.speechSynthesis.speak(utterance);
}

export function stopBriefing(): void {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}
