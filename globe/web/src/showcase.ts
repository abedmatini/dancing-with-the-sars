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

export async function loadShowcase(): Promise<ShowcaseSpot | null> {
  const response = await fetch("/showcase/western-cape/manifest.json");
  if (!response.ok) return null;
  return (await response.json()) as ShowcaseSpot;
}
