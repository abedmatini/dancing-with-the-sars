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

function seasonNotes(date: string, lat: number): { opening: string; farm: string } {
  const month = Number(date.slice(5, 7)) || 6;
  const southern = lat < 0;
  let season = "autumn";
  if (month === 12 || month <= 2) season = southern ? "summer" : "winter";
  else if (month <= 5) season = southern ? "autumn" : "spring";
  else if (month <= 8) season = southern ? "winter" : "summer";
  else season = southern ? "spring" : "autumn";
  const harvest = (!southern && month >= 8 && month <= 11) || (southern && (month >= 11 || month <= 3));
  if (harvest) {
    return {
      opening: `It is ${season}, and farmers are in harvest.`,
      farm: "A farmer in harvest season times water from the rain and soil.",
    };
  }
  if ((season === "spring" || season === "autumn") && [3, 4, 5, 9, 10].includes(month)) {
    return {
      opening: `It is ${season}, when many farmers are planting.`,
      farm: "A farmer at planting times the first water from the rain and soil.",
    };
  }
  if (season === "summer") {
    return {
      opening: `It is ${season}, and growers are irrigating.`,
      farm: "A farmer mid-season uses the rain and soil to plan irrigation.",
    };
  }
  return {
    opening: `It is ${season}, a quieter stretch for many crops.`,
    farm: "A farmer in the off-season uses the rain and soil to plan stored water.",
  };
}

/** About 30 seconds when read aloud. Uses only numbers already on the scene. */
export function briefingScript(scene: Scene, date: string): string {
  const soil = scene.soil_moisture.map((row) => row.value);
  const first = soil[0] ?? scene.soil_value;
  const selected = scene.soil_moisture.find((row) => row.date === date)?.value ?? soil[soil.length - 1] ?? scene.soil_value;
  const risk = scene.risk_series.find((row) => row.date === date) ?? scene.risk;
  const soilShort =
    scene.soil_available === false || soil.length === 0
      ? "unavailable"
      : selected > first + 0.01
        ? "up since the first scene"
        : selected < first - 0.01
          ? "down since the first scene"
          : "about the same as the first scene";
  const { opening, farm } = seasonNotes(date, scene.lat);
  const source = scene.using_mock ? "This is the seeded demo" : "This uses the loaded satellite series";
  return (
    `${scene.name}, ${date}. ${opening} ` +
    `Rain is ${Math.round(scene.percent_normal)} percent of normal. Soil is ${soilShort}. ` +
    `Runoff is ${risk.class}, ${Math.round(risk.score)} out of 100. ` +
    `Burned share is ${Math.round(scene.burned_percent)} percent, on a ${Math.round(scene.slope.mean)} degree slope. ` +
    `A land buyer uses this as a dryness check. ${farm} ` +
    `A fire crew watches steep burned slopes, which shed sediment after rain. ` +
    `An insurer treats ${risk.class} as today's flag, not a promise. ` +
    `${source}. This reading is not a climate forecast and not advice to buy or walk away.`
  );
}

type VoiceStatus = (message: string) => void;

let speakToken = 0;
let audioEl: HTMLAudioElement | null = null;
let voicePromise: Promise<import("kokoro-js").KokoroTTS | null> | null = null;

export function stopBriefing(): void {
  speakToken += 1;
  if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel();
  if (audioEl) {
    audioEl.pause();
    audioEl.src = "";
    audioEl = null;
  }
}

async function neuralVoice(onStatus: VoiceStatus) {
  voicePromise ??= (async () => {
    try {
      onStatus("Loading a natural voice…");
      const { KokoroTTS } = await import("kokoro-js");
      return await KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", {
        dtype: "q4",
        device: "wasm",
        progress_callback: (info) => {
          const progress = info as { status?: string; loaded?: number; total?: number };
          if (progress.total && progress.loaded) {
            onStatus(`Loading a natural voice… ${Math.round((100 * progress.loaded) / progress.total)}%`);
          }
        },
      });
    } catch {
      return null;
    }
  })();
  return voicePromise;
}

function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const ranked = voices
    .filter((voice) => voice.lang.toLowerCase().startsWith("en"))
    .map((voice) => {
      const name = voice.name.toLowerCase();
      let score = 8;
      if (name.includes("natural") || name.includes("neural") || name.includes("premium")) score = 0;
      else if (/(samantha|daniel|aria|jenny|guy|bella)/.test(name)) score = 1;
      else if (name.includes("google uk english female")) score = 2;
      else if (name.includes("google us english")) score = 4;
      return { voice, score };
    })
    .sort((left, right) => left.score - right.score);
  return ranked[0]?.voice ?? null;
}

function browserSpeech(text: string, token: number): Promise<void> {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) {
      resolve();
      return;
    }
    const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) ?? [text];
    const speak = () => {
      if (token !== speakToken) {
        resolve();
        return;
      }
      const voice = pickVoice(window.speechSynthesis.getVoices());
      let index = 0;
      const next = () => {
        if (token !== speakToken || index >= sentences.length) {
          resolve();
          return;
        }
        const utterance = new SpeechSynthesisUtterance(sentences[index]?.trim() ?? "");
        index += 1;
        if (voice) utterance.voice = voice;
        utterance.lang = voice?.lang ?? "en-US";
        utterance.rate = 0.94;
        utterance.pitch = 1;
        utterance.onend = () => window.setTimeout(next, 180);
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
      };
      next();
    };
    if (window.speechSynthesis.getVoices().length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null;
        speak();
      };
      window.setTimeout(speak, 350);
      return;
    }
    speak();
  });
}

/** Prefer a local neural voice. Fall back to the best browser voice, with pauses. */
export async function speakBriefing(text: string, onStatus: VoiceStatus = () => undefined): Promise<void> {
  const token = ++speakToken;
  if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel();
  if (audioEl) {
    audioEl.pause();
    audioEl = null;
  }
  try {
    const model = await neuralVoice(onStatus);
    if (token !== speakToken || !model) {
      if (token === speakToken) await browserSpeech(text, token);
      return;
    }
    onStatus("Preparing the briefing…");
    const clip = await model.generate(text, { voice: "af_heart", speed: 1.05 });
    if (token !== speakToken) return;
    const url = URL.createObjectURL(clip.toBlob());
    const audio = new Audio(url);
    audioEl = audio;
    onStatus("");
    try {
      await audio.play();
    } catch {
      URL.revokeObjectURL(url);
      audioEl = null;
      if (token === speakToken) await browserSpeech(text, token);
      return;
    }
    await new Promise<void>((resolve) => {
      audio.onended = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
    });
  } catch {
    if (token === speakToken) await browserSpeech(text, token);
  }
}
