import {
  CallbackPositionProperty,
  Cartesian2,
  Cartesian3,
  Cartographic,
  Color,
  CzmlDataSource,
  Ellipsoid,
  EllipsoidalOccluder,
  EllipsoidTerrainProvider,
  ImageMaterialProperty,
  Ion,
  JulianDate,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  PolylineGlowMaterialProperty,
  Rectangle,
  SceneTransforms,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Terrain,
  VerticalOrigin,
  type ImageryLayer,
} from "cesium";
import { useEffect, useMemo, useRef, useState } from "react";
import { Entity, useCesium, Viewer } from "resium";
import { baseLayer, detailProvider, fireProvider, MODIS_TRUE_COLOR_DATES, modisProvider, soilProvider } from "./imagery";
import { satelliteCzml } from "./satellites";
import type { ShowcaseSpot } from "./showcase";
import type { FlowPath, RiskGrid, SitePin } from "./types";
import { windStrength, type WindField } from "./wind";

const HOME_VIEW = { lon: 18, lat: -22, height: 21_000_000 };
const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
if (ionToken) Ion.defaultAccessToken = ionToken;

const ellipsoidTerrain = new EllipsoidTerrainProvider();
const pinScale = new NearFarScalar(2e5, 1.2, 2.2e7, 0.7);
const BOX_SCALE = 1.65;

function arrowImage(): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = 48;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  ctx.clearRect(0, 0, 48, 64);
  ctx.fillStyle = "rgba(226, 242, 255, 0.92)";
  ctx.beginPath();
  ctx.moveTo(24, 6);
  ctx.lineTo(36, 28);
  ctx.lineTo(28, 28);
  ctx.lineTo(28, 56);
  ctx.lineTo(20, 56);
  ctx.lineTo(20, 28);
  ctx.lineTo(12, 28);
  ctx.closePath();
  ctx.fill();
  return canvas;
}

function showcasePinImage(): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  ctx.clearRect(0, 0, 128, 128);
  ctx.beginPath();
  ctx.arc(64, 64, 56, 0, Math.PI * 2);
  ctx.fillStyle = "#041018";
  ctx.fill();
  ctx.lineWidth = 8;
  ctx.strokeStyle = "#f6c453";
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(64, 64, 22, 0, Math.PI * 2);
  ctx.fillStyle = "#f6c453";
  ctx.fill();
  return canvas;
}

const showcaseMarker = showcasePinImage();
const arrowMarker = arrowImage();

type FlyTarget = { lat: number; lon: number; key: number };

function riskColor(score: number): Color {
  const clamped = Math.min(100, Math.max(0, score)) / 100;
  const hue = 128 - clamped * 128;
  return Color.fromHsl(hue / 360, 0.85, 0.5, 0.78);
}

function grownBounds(grid: RiskGrid) {
  const lat = (grid.north + grid.south) / 2;
  const lon = (grid.east + grid.west) / 2;
  const halfLat = ((grid.north - grid.south) / 2) * BOX_SCALE;
  const halfLon = ((grid.east - grid.west) / 2) * BOX_SCALE;
  return {
    west: lon - halfLon,
    east: lon + halfLon,
    south: lat - halfLat,
    north: lat + halfLat,
  };
}

function frameHeight(west: number, south: number, east: number, north: number): number {
  const lat = (south + north) / 2;
  const widthM = Math.abs(east - west) * 111_320 * Math.cos((lat * Math.PI) / 180);
  const heightM = Math.abs(north - south) * 110_540;
  const span = Math.max(widthM, heightM, 4_000);
  const visible = span / 0.5;
  const height = visible / 2 / Math.tan(Math.PI / 6);
  return Math.min(60_000, Math.max(9_000, height));
}

function paintHeat(grid: RiskGrid): HTMLCanvasElement {
  const source = document.createElement("canvas");
  source.width = Math.max(1, grid.cols);
  source.height = Math.max(1, grid.rows);
  const sourceContext = source.getContext("2d");
  const output = document.createElement("canvas");
  output.width = Math.max(1, grid.cols) * 16;
  output.height = Math.max(1, grid.rows) * 16;
  if (!sourceContext) return output;
  const pixels = sourceContext.createImageData(source.width, source.height);
  for (let row = 0; row < source.height; row += 1) {
    for (let col = 0; col < source.width; col += 1) {
      const [red, green, blue, alpha] = riskColor(grid.values[row]?.[col] ?? 0).toBytes();
      const index = (row * source.width + col) * 4;
      pixels.data[index] = red;
      pixels.data[index + 1] = green;
      pixels.data[index + 2] = blue;
      pixels.data[index + 3] = alpha;
    }
  }
  sourceContext.putImageData(pixels, 0, 0);
  const outputContext = output.getContext("2d");
  if (!outputContext) return source;
  outputContext.imageSmoothingEnabled = false;
  outputContext.drawImage(source, 0, 0, output.width, output.height);
  return output;
}

function blendHeat(from: HTMLCanvasElement, to: HTMLCanvasElement, amount: number): HTMLCanvasElement {
  const output = document.createElement("canvas");
  output.width = to.width;
  output.height = to.height;
  const ctx = output.getContext("2d");
  if (!ctx) return to;
  ctx.drawImage(from, 0, 0, output.width, output.height);
  ctx.globalAlpha = amount;
  ctx.drawImage(to, 0, 0, output.width, output.height);
  return output;
}

function useFadingHeat(grid: RiskGrid | null): HTMLCanvasElement | null {
  const [frame, setFrame] = useState<HTMLCanvasElement | null>(null);
  const previous = useRef<HTMLCanvasElement | null>(null);
  const previousDate = useRef<string | null>(null);
  useEffect(() => {
    if (!grid) {
      setFrame(null);
      previous.current = null;
      previousDate.current = null;
      return;
    }
    const next = paintHeat(grid);
    const from = previous.current;
    const same = previousDate.current === grid.date;
    previous.current = next;
    previousDate.current = grid.date;
    if (!from || same) {
      setFrame(next);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 900);
      const eased = t * t * (3 - 2 * t);
      setFrame(blendHeat(from, next, eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [grid]);
  return frame;
}

function driftingPosition(lat: number, lon: number, directionFrom: number, speed: number) {
  const to = (((directionFrom + 180) % 360) * Math.PI) / 180;
  const step = Math.min(0.02, 0.004 + speed / 2500);
  return new CallbackPositionProperty((time) => {
    const ms = time ? JulianDate.toDate(time).getTime() : Date.now();
    const phase = (ms % 6000) / 6000;
    const lat2 = lat + Math.cos(to) * step * phase;
    const lon2 = lon + (Math.sin(to) * step * phase) / Math.max(0.25, Math.cos((lat * Math.PI) / 180));
    return Cartesian3.fromDegrees(lon2, lat2, 700);
  }, false);
}

function GlobeEffects({
  basemap,
  pins,
  target,
  grid,
  spinning,
  showDaily,
  showFire,
  showSoil,
  showSatellites,
  onStopSpin,
  onPick,
  onShowcase,
  radarSpot,
  radarOpen,
  radarFly,
  onRadarAnchor,
  zoomStep,
  homeStep,
}: {
  basemap: "gibs" | "osm";
  pins: SitePin[];
  target: FlyTarget | null;
  grid: RiskGrid | null;
  spinning: boolean;
  showDaily: boolean;
  showFire: boolean;
  showSoil: boolean;
  showSatellites: boolean;
  onStopSpin: () => void;
  onPick: (lat: number, lon: number) => void;
  onShowcase: (id: string) => void;
  radarSpot: ShowcaseSpot | null;
  radarOpen: boolean;
  radarFly: number;
  onRadarAnchor: (point: { x: number; y: number } | null) => void;
  zoomStep: number;
  homeStep: number;
}) {
  const { viewer } = useCesium();
  const stopRef = useRef(onStopSpin);
  const pickRef = useRef(onPick);
  const showcaseRef = useRef(onShowcase);
  const pinsRef = useRef(pins);
  const radarRef = useRef(radarSpot);
  const anchorRef = useRef(onRadarAnchor);
  stopRef.current = onStopSpin;
  pickRef.current = onPick;
  showcaseRef.current = onShowcase;
  pinsRef.current = pins;
  radarRef.current = radarSpot;
  anchorRef.current = onRadarAnchor;

  useEffect(() => {
    if (!viewer) return;
    viewer.camera.setView({
      destination: Cartesian3.fromDegrees(HOME_VIEW.lon, HOME_VIEW.lat, HOME_VIEW.height),
    });
    viewer.scene.backgroundColor = Color.fromCssColorString("#071018");
    viewer.scene.globe.baseColor = Color.fromCssColorString("#102033");
    viewer.scene.globe.enableLighting = false;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    viewer.scene.globe.maximumScreenSpaceError = 1.1;
  }, [viewer]);

  useEffect(() => {
    if (!viewer || !spinning) return;
    const remove = viewer.scene.postUpdate.addEventListener(() => {
      viewer.camera.rotateRight(0.00032);
    });
    return () => remove();
  }, [viewer, spinning]);

  useEffect(() => {
    if (!viewer) return;
    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    const stop = () => stopRef.current();
    handler.setInputAction(stop, ScreenSpaceEventType.LEFT_DOWN);
    handler.setInputAction(stop, ScreenSpaceEventType.WHEEL);
    handler.setInputAction(stop, ScreenSpaceEventType.PINCH_START);
    handler.setInputAction((click: ScreenSpaceEventHandler.PositionedEvent) => {
      stop();
      const picked = viewer.scene.pick(click.position);
      const entityId = picked?.id?.id;
      if (typeof entityId === "string" && entityId.startsWith("showcase:")) {
        showcaseRef.current(entityId.slice("showcase:".length));
        return;
      }
      const pin =
        typeof entityId === "string" ? pinsRef.current.find((site) => site.id === entityId) : undefined;
      if (pin) {
        pickRef.current(pin.lat, pin.lon);
        return;
      }
      const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
      if (!cartesian) return;
      const cartographic = Cartographic.fromCartesian(cartesian);
      pickRef.current(CesiumMath.toDegrees(cartographic.latitude), CesiumMath.toDegrees(cartographic.longitude));
    }, ScreenSpaceEventType.LEFT_CLICK);
    return () => handler.destroy();
  }, [viewer]);

  useEffect(() => {
    if (!viewer || !target) return;
    const bounds = grid ? grownBounds(grid) : null;
    const height = bounds ? frameHeight(bounds.west, bounds.south, bounds.east, bounds.north) : 18_000;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(target.lon, target.lat, height),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
      duration: 1.6,
    });
  }, [viewer, target, grid?.west, grid?.south, grid?.east, grid?.north]);

  useEffect(() => {
    if (!viewer || homeStep === 0) return;
    viewer.camera.cancelFlight();
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(HOME_VIEW.lon, HOME_VIEW.lat, HOME_VIEW.height),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
      duration: 1.4,
    });
  }, [viewer, homeStep]);

  const zoomSeen = useRef(zoomStep);
  useEffect(() => {
    if (!viewer || zoomStep === zoomSeen.current) return;
    const inward = zoomStep > zoomSeen.current;
    zoomSeen.current = zoomStep;
    const height = viewer.camera.positionCartographic.height;
    const distance = Math.max(400, height * 0.45);
    if (inward) viewer.camera.zoomIn(distance);
    else viewer.camera.zoomOut(distance);
  }, [viewer, zoomStep]);

  useEffect(() => {
    if (!viewer || basemap !== "gibs") return;
    const layer = viewer.imageryLayers.addImageryProvider(detailProvider());
    layer.show = false;
    const update = () => {
      if (viewer.isDestroyed()) return;
      layer.show = viewer.camera.positionCartographic.height < 1_200_000;
    };
    viewer.camera.percentageChanged = 0.08;
    const removeChanged = viewer.camera.changed.addEventListener(update);
    update();
    return () => {
      removeChanged();
      if (!viewer.isDestroyed()) viewer.imageryLayers.remove(layer, true);
    };
  }, [viewer, basemap]);

  useEffect(() => {
    if (!viewer) return;
    const added: ImageryLayer[] = [];
    if (showDaily) {
      // Black orbit gaps in one day were showing the blue basemap as stripes.
      // Earlier days sit underneath and fill those gaps. Near-black pixels are punched out.
      for (const date of MODIS_TRUE_COLOR_DATES) {
        const layer = viewer.imageryLayers.addImageryProvider(modisProvider(date));
        layer.colorToAlpha = Color.BLACK;
        layer.colorToAlphaThreshold = 0.22;
        added.push(layer);
      }
    }
    if (showFire) {
      const layer = viewer.imageryLayers.addImageryProvider(fireProvider());
      layer.alpha = 0.9;
      added.push(layer);
    }
    if (showSoil) {
      const layer = viewer.imageryLayers.addImageryProvider(soilProvider());
      layer.alpha = 0.55;
      added.push(layer);
    }
    return () => {
      if (viewer.isDestroyed()) return;
      for (const layer of added) viewer.imageryLayers.remove(layer, true);
    };
  }, [viewer, showDaily, showFire, showSoil]);

  useEffect(() => {
    if (!viewer) return;
    if (!showSatellites) {
      viewer.clock.shouldAnimate = false;
      return;
    }
    let cancelled = false;
    let source: CzmlDataSource | null = null;
    const height = viewer.camera.positionCartographic.height;
    if (height < 8_000_000) {
      const place = viewer.camera.positionCartographic;
      viewer.camera.flyTo({
        destination: Cartesian3.fromRadians(place.longitude, place.latitude, 16_000_000),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
        duration: 1.5,
      });
    }
    void CzmlDataSource.load(satelliteCzml()).then((loaded) => {
      if (cancelled || viewer.isDestroyed()) return;
      source = loaded;
      viewer.dataSources.add(loaded);
      viewer.clock.shouldAnimate = true;
      viewer.clock.multiplier = 160;
    });
    return () => {
      cancelled = true;
      if (source && !viewer.isDestroyed()) viewer.dataSources.remove(source, true);
      if (!viewer.isDestroyed()) viewer.clock.shouldAnimate = false;
    };
  }, [viewer, showSatellites]);

  useEffect(() => {
    if (!viewer) return;
    const occluder = new EllipsoidalOccluder(Ellipsoid.WGS84, Cartesian3.ZERO);
    const hideFarSide = () => {
      if (viewer.isDestroyed()) return;
      occluder.cameraPosition = viewer.camera.positionWC;
      for (const entity of viewer.entities.values) {
        if (typeof entity.id !== "string" || !entity.id.startsWith("showcase:")) continue;
        const position = entity.position?.getValue(viewer.clock.currentTime);
        entity.show = Boolean(position && occluder.isPointVisible(position));
      }
    };
    const remove = viewer.scene.preRender.addEventListener(hideFarSide);
    return () => remove();
  }, [viewer]);

  useEffect(() => {
    if (!viewer || radarFly === 0 || !radarRef.current) return;
    const spot = radarRef.current;
    viewer.camera.cancelFlight();
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(spot.lon, spot.lat, 2_600_000),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
      duration: 1.3,
    });
  }, [viewer, radarFly]);

  useEffect(() => {
    if (!viewer) return;
    const tick = () => {
      const spot = radarOpen ? radarRef.current : null;
      if (!spot || viewer.isDestroyed()) {
        anchorRef.current(null);
        return;
      }
      const cartesian = Cartesian3.fromDegrees(spot.lon, spot.lat, 200);
      const occluder = new EllipsoidalOccluder(Ellipsoid.WGS84, viewer.camera.positionWC);
      if (!occluder.isPointVisible(cartesian)) {
        anchorRef.current(null);
        return;
      }
      const canvas = viewer.scene.canvas;
      const pos = SceneTransforms.worldToWindowCoordinates(viewer.scene, cartesian);
      if (!pos) {
        anchorRef.current(null);
        return;
      }
      const rect = canvas.getBoundingClientRect();
      anchorRef.current({ x: rect.left + pos.x, y: rect.top + pos.y });
    };
    const remove = viewer.scene.postRender.addEventListener(tick);
    return () => {
      remove();
      anchorRef.current(null);
    };
  }, [viewer, radarOpen]);

  return null;
}

export function Earth({
  basemap,
  pins,
  grid,
  flow,
  wind,
  target,
  spinning,
  showDaily,
  showFire,
  showSoil,
  showSatellites,
  showRisk,
  onStopSpin,
  onPick,
  onShowcase,
  radarSpots,
  radarSpot,
  radarOpen,
  radarFly,
  onRadarAnchor,
  zoomStep,
  homeStep,
}: {
  basemap: "gibs" | "osm";
  pins: SitePin[];
  grid: RiskGrid | null;
  flow: FlowPath | null;
  wind: WindField | null;
  target: FlyTarget | null;
  spinning: boolean;
  showDaily: boolean;
  showFire: boolean;
  showSoil: boolean;
  showSatellites: boolean;
  showRisk: boolean;
  onStopSpin: () => void;
  onPick: (lat: number, lon: number) => void;
  onShowcase: (id: string) => void;
  radarSpots: ShowcaseSpot[];
  radarSpot: ShowcaseSpot | null;
  radarOpen: boolean;
  radarFly: number;
  onRadarAnchor: (point: { x: number; y: number } | null) => void;
  zoomStep: number;
  homeStep: number;
}) {
  const imagery = useMemo(() => baseLayer(basemap), [basemap]);
  const heat = useFadingHeat(grid);
  const bounds = grid ? grownBounds(grid) : null;
  const windMarks = useMemo(
    () =>
      (wind?.arrows ?? []).map((arrow) => ({
        ...arrow,
        position: driftingPosition(arrow.lat, arrow.lon, arrow.direction_deg, arrow.speed_kmh),
        rotation: -CesiumMath.toRadians((arrow.direction_deg + 180) % 360),
      })),
    [wind],
  );
  return (
    <Viewer
      key={basemap}
      full
      baseLayer={imagery}
      terrain={ionToken ? Terrain.fromWorldTerrain() : undefined}
      terrainProvider={ionToken ? undefined : ellipsoidTerrain}
      animation={false}
      timeline={false}
      baseLayerPicker={false}
      geocoder={false}
      homeButton={false}
      sceneModePicker={false}
      navigationHelpButton={false}
      infoBox={false}
      selectionIndicator={false}
      fullscreenButton={false}
      skyAtmosphere={false}
    >
      <GlobeEffects
        basemap={basemap}
        pins={pins}
        target={target}
        grid={grid}
        spinning={spinning}
        showDaily={showDaily}
        showFire={showFire}
        showSoil={showSoil}
        showSatellites={showSatellites}
        onStopSpin={onStopSpin}
        onPick={onPick}
        onShowcase={onShowcase}
        radarSpot={radarSpot}
        radarOpen={radarOpen}
        radarFly={radarFly}
        onRadarAnchor={onRadarAnchor}
        zoomStep={zoomStep}
        homeStep={homeStep}
      />
      {radarSpots.map((spot) => (
        <Entity
          key={spot.id}
          id={`showcase:${spot.id}`}
          name={spot.name}
          position={Cartesian3.fromDegrees(spot.lon, spot.lat, 80)}
          billboard={{
            image: showcaseMarker,
            width: 64,
            height: 64,
            verticalOrigin: VerticalOrigin.CENTER,
            scaleByDistance: pinScale,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          }}
          label={{
            text: spot.name,
            font: "600 15px sans-serif",
            fillColor: Color.fromCssColorString("#f6c453"),
            outlineColor: Color.fromCssColorString("#041018"),
            outlineWidth: 3,
            style: LabelStyle.FILL_AND_OUTLINE,
            pixelOffset: new Cartesian2(0, 36),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            scaleByDistance: new NearFarScalar(2e5, 1, 1.2e7, 0.7),
          }}
        />
      ))}
      {showRisk && grid && bounds ? (
        <Entity
          polyline={{
            positions: Cartesian3.fromDegreesArrayHeights([
              bounds.west, bounds.south, 500,
              bounds.east, bounds.south, 500,
              bounds.east, bounds.north, 500,
              bounds.west, bounds.north, 500,
              bounds.west, bounds.south, 500,
            ]),
            width: 4,
            material: Color.fromCssColorString("#7ee7ff"),
          }}
        />
      ) : null}
      {showRisk && grid && bounds && heat ? (
        <Entity
          rectangle={{
            coordinates: Rectangle.fromDegrees(bounds.west, bounds.south, bounds.east, bounds.north),
            material: new ImageMaterialProperty({ image: heat, transparent: true }),
            height: 400,
          }}
        />
      ) : null}
      {flow && flow.coordinates.length > 1 ? (
        <Entity
          polyline={{
            positions: Cartesian3.fromDegreesArrayHeights(flow.coordinates.flatMap(([lon, lat]) => [lon, lat, 1200])),
            width: 4,
            material: new PolylineGlowMaterialProperty({
              color: Color.fromCssColorString("#9ad7ff"),
            }),
          }}
        />
      ) : null}
      {flow?.rivers.map((river) => (
        <Entity
          key={`${river.name}-${river.lon}-${river.lat}`}
          position={Cartesian3.fromDegrees(river.lon, river.lat, 1400)}
          label={{
            text: river.name,
            font: "600 15px sans-serif",
            fillColor: Color.WHITE,
            outlineColor: Color.fromCssColorString("#041018"),
            outlineWidth: 3,
            style: LabelStyle.FILL_AND_OUTLINE,
            pixelOffset: new Cartesian2(0, -18),
            disableDepthTestDistance: 800_000,
            scaleByDistance: new NearFarScalar(2e4, 1, 4e6, 0.45),
          }}
        />
      ))}
      {windMarks.map((arrow) => (
        <Entity
          key={`${arrow.lat.toFixed(3)}-${arrow.lon.toFixed(3)}`}
          position={arrow.position}
          billboard={{
            image: arrowMarker,
            width: 22 * windStrength(arrow.speed_kmh).scale,
            height: 30 * windStrength(arrow.speed_kmh).scale,
            rotation: arrow.rotation,
            verticalOrigin: VerticalOrigin.CENTER,
            disableDepthTestDistance: 0,
          }}
        />
      ))}
    </Viewer>
  );
}
