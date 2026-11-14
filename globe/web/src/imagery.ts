import {
  Credit,
  ImageryLayer,
  OpenStreetMapImageryProvider,
  UrlTemplateImageryProvider,
  WebMapServiceImageryProvider,
  WebMercatorTilingScheme,
} from "cesium";

const TRUE_COLOR_DATE = "2026-10-15";
// One MODIS day leaves black gaps between orbits. Earlier days cover those gaps.
export const MODIS_TRUE_COLOR_DATES = ["2026-10-13", "2026-10-14", TRUE_COLOR_DATE];
const SOIL_DATE = "2026-05-16";
const mercator = () => new WebMercatorTilingScheme();
const credit = (text: string) => new Credit(text);

export function baseLayer(kind: "gibs" | "osm"): ImageryLayer {
  if (kind === "osm") {
    return new ImageryLayer(
      new OpenStreetMapImageryProvider({
        url: "https://tile.openstreetmap.org/",
        credit: credit("© OpenStreetMap contributors"),
      }),
    );
  }
  return new ImageryLayer(
    new UrlTemplateImageryProvider({
      url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
      credit: credit("NASA GIBS · Blue Marble"),
      tilingScheme: mercator(),
      maximumLevel: 8,
    }),
  );
}

export function modisProvider(date = TRUE_COLOR_DATE): UrlTemplateImageryProvider {
  return new UrlTemplateImageryProvider({
    url: `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpeg`,
    credit: credit(`NASA GIBS · MODIS Terra true colour ${date}`),
    tilingScheme: mercator(),
    maximumLevel: 8,
  });
}

export function fireProvider(): WebMapServiceImageryProvider {
  return new WebMapServiceImageryProvider({
    url: "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi",
    layers: "MODIS_Terra_Thermal_Anomalies_All",
    parameters: {
      transparent: true,
      format: "image/png",
      time: TRUE_COLOR_DATE,
    },
    credit: credit("NASA GIBS · MODIS Terra thermal anomalies"),
    maximumLevel: 5,
    enablePickFeatures: false,
  });
}

export function soilProvider(): UrlTemplateImageryProvider {
  return new UrlTemplateImageryProvider({
    url: `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/SMAP_L4_Analyzed_Surface_Soil_Moisture/default/${SOIL_DATE}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`,
    credit: credit(`NASA GIBS · SMAP L4 surface soil moisture ${SOIL_DATE}`),
    tilingScheme: new WebMercatorTilingScheme(),
    maximumLevel: 6,
  });
}
