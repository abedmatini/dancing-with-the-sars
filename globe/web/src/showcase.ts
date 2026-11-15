export type ShowcaseFrame = {
  date: string;
  label: string;
  src: string;
};

export type ShowcaseSpot = {
  id: string;
  name: string;
  region: string;
  lat: number;
  lon: number;
  story: string;
  frames: ShowcaseFrame[];
};

export async function loadShowcase(): Promise<ShowcaseSpot[]> {
  const response = await fetch("/showcase/index.json");
  if (!response.ok) return [];
  const payload = (await response.json()) as { spots: ShowcaseSpot[] };
  return payload.spots.filter((spot) => spot.frames.length > 0);
}
