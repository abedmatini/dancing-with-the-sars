export type SourceMode = "mock" | "earthdata";

export type SitePin = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  coordinates: string;
  west: number;
  south: number;
  east: number;
  north: number;
  terrain: string;
  description: string;
};

export type Catalog = {
  groups: { name: string; sites: SitePin[] }[];
};

export type RainRow = {
  time: string;
  observed_mm: number;
  climatology_mm: number;
  anomaly_mm: number;
  percent_normal: number;
};

export type Scene = {
  id: string;
  name: string;
  description: string;
  lat: number;
  lon: number;
  coordinates: string;
  west: number;
  south: number;
  east: number;
  north: number;
  terrain: string;
  source: SourceMode;
  using_mock: boolean;
  layers: Record<string, string>;
  notice: string;
  date: string;
  dates: string[];
  rainfall: RainRow[];
  rainfall_month: string;
  percent_normal: number;
  anomaly_mm: number;
  climatology_name: string;
  soil_moisture: { date: string; value: number; units: string }[];
  soil_value: number;
  soil_unit: string;
  slope: { mean: number; min: number; max: number; units: string };
  risk: { score: number; class: string; ranges: string };
  risk_series: { date: string; score: number; class: string }[];
  burned_percent: number;
};

export type RiskGrid = {
  date: string;
  west: number;
  south: number;
  east: number;
  north: number;
  rows: number;
  cols: number;
  values: number[][];
};

export type DemoFile = {
  sites: Catalog;
  scenes: Record<string, { scene: Scene; grids: Record<string, RiskGrid> }>;
};

export type ChatTurn = { role: "user" | "assistant"; text: string };

export type FlowPath = {
  coordinates: [number, number][];
  rivers: { name: string; lon: number; lat: number }[];
  summary: string;
  credit: string;
};
