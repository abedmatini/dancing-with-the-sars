import {
  Cartesian3,
  Cartographic,
  Color,
  EllipsoidTerrainProvider,
  Ion,
  Math as CesiumMath,
  Rectangle,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Terrain,
  type ImageryLayer,
} from "cesium";
import { useEffect, useMemo, useRef } from "react";
import { Entity, useCesium, Viewer } from "resium";
import { baseLayer, fireProvider, modisProvider, soilProvider } from "./imagery";
import type { RiskGrid, SitePin } from "./types";

const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
if (ionToken) Ion.defaultAccessToken = ionToken;

const ellipsoidTerrain = new EllipsoidTerrainProvider();

type FlyTarget = { lat: number; lon: number; key: number };

function riskColor(score: number): Color {
  const clamped = Math.min(100, Math.max(0, score)) / 100;
  const hue = 128 - clamped * 128;
  return Color.fromHsl(hue / 360, 0.85, 0.5, 0.78);
}

function GlobeEffects({
  pins,
  target,
  spinning,
  showDaily,
  showFire,
  showSoil,
  onStopSpin,
  onPick,
}: {
  pins: SitePin[];
  target: FlyTarget | null;
  spinning: boolean;
  showDaily: boolean;
  showFire: boolean;
  showSoil: boolean;
  onStopSpin: () => void;
  onPick: (lat: number, lon: number) => void;
}) {
  const { viewer } = useCesium();
  const stopRef = useRef(onStopSpin);
  const pickRef = useRef(onPick);
  const pinsRef = useRef(pins);
  stopRef.current = onStopSpin;
  pickRef.current = onPick;
  pinsRef.current = pins;

  useEffect(() => {
    if (!viewer) return;
    viewer.camera.setView({ destination: Cartesian3.fromDegrees(18, -22, 21000000) });
    viewer.scene.backgroundColor = Color.fromCssColorString("#071018");
    viewer.scene.globe.baseColor = Color.fromCssColorString("#102033");
    viewer.scene.globe.enableLighting = false;
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
        const pin =
          typeof entityId === "string"
            ? pinsRef.current.find((site) => site.id === entityId)
            : undefined;
        if (pin) {
          pickRef.current(pin.lat, pin.lon);
          return;
        }
        const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
        if (!cartesian) return;
        const cartographic = Cartographic.fromCartesian(cartesian);
        pickRef.current(
          CesiumMath.toDegrees(cartographic.latitude),
          CesiumMath.toDegrees(cartographic.longitude),
        );
    }, ScreenSpaceEventType.LEFT_CLICK);
    return () => handler.destroy();
  }, [viewer]);

  useEffect(() => {
    if (!viewer || !target) return;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(target.lon, target.lat, 28000),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
      duration: 2.4,
    });
  }, [viewer, target]);

  useEffect(() => {
    if (!viewer) return;
    const added: ImageryLayer[] = [];
    if (showDaily) {
      const layer = viewer.imageryLayers.addImageryProvider(modisProvider());
      layer.colorToAlpha = Color.BLACK;
      layer.colorToAlphaThreshold = 0.05;
      added.push(layer);
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

  return null;
}

function cells(grid: RiskGrid) {
  const lonStep = (grid.east - grid.west) / grid.cols;
  const latStep = (grid.north - grid.south) / grid.rows;
  const items: { key: string; west: number; south: number; east: number; north: number; score: number }[] = [];
  for (let row = 0; row < grid.rows; row += 1) {
    for (let col = 0; col < grid.cols; col += 1) {
      const north = grid.north - row * latStep;
      items.push({
        key: `${grid.date}-${row}-${col}`,
        west: grid.west + col * lonStep,
        east: grid.west + (col + 1) * lonStep,
        north,
        south: north - latStep,
        score: grid.values[row]?.[col] ?? 0,
      });
    }
  }
  return items;
}

export function Earth({
  basemap,
  pins,
  grid,
  target,
  spinning,
  showDaily,
  showFire,
  showSoil,
  onStopSpin,
  onPick,
}: {
  basemap: "gibs" | "osm";
  pins: SitePin[];
  grid: RiskGrid | null;
  target: FlyTarget | null;
  spinning: boolean;
  showDaily: boolean;
  showFire: boolean;
  showSoil: boolean;
  onStopSpin: () => void;
  onPick: (lat: number, lon: number) => void;
}) {
  const imagery = useMemo(() => baseLayer(basemap), [basemap]);
  const draped = grid ? cells(grid) : [];
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
        pins={pins}
        target={target}
        spinning={spinning}
        showDaily={showDaily && basemap === "gibs"}
        showFire={showFire}
        showSoil={showSoil}
        onStopSpin={onStopSpin}
        onPick={onPick}
      />
      {pins.map((site) => (
        <Entity
          key={site.id}
          id={site.id}
          name={site.name}
          position={Cartesian3.fromDegrees(site.lon, site.lat, 2000)}
          point={{
            pixelSize: 14,
            color: Color.fromCssColorString("#7ee7ff"),
            outlineColor: Color.fromCssColorString("#e8fbff"),
            outlineWidth: 3,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          }}
        />
      ))}
      {grid ? (
        <Entity
          polyline={{
            positions: Cartesian3.fromDegreesArrayHeights([
              grid.west, grid.south, 500,
              grid.east, grid.south, 500,
              grid.east, grid.north, 500,
              grid.west, grid.north, 500,
              grid.west, grid.south, 500,
            ]),
            width: 3,
            material: Color.fromCssColorString("#7ee7ff"),
          }}
        />
      ) : null}
      {draped.map((cell) => (
        <Entity
          key={cell.key}
          rectangle={{
            coordinates: Rectangle.fromDegrees(cell.west, cell.south, cell.east, cell.north),
            material: riskColor(cell.score),
            height: 400,
          }}
        />
      ))}
    </Viewer>
  );
}
