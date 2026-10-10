import { PathStyleExtension } from "@deck.gl/extensions";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";
import type { DistrictProps, Feature, FeatureCollection, Hazard, SignalProps, ZoneProps } from "@/lib/api/types";
import { HAZARDS } from "@/lib/hazards";

export type LayerInput = {
  districts: FeatureCollection<DistrictProps>;
  zones: FeatureCollection<ZoneProps>;
  signals: FeatureCollection<SignalProps>;
  hazard: Hazard;
  time: number; // seconds; drives the "breathing" of active zones (held at 0 for reduced motion)
  pulseIds: Set<string>;
  onZoneClick?: (zone: Feature<ZoneProps>) => void;
};

type RGBA = [number, number, number, number];
const BAND_ALPHA = { none: 0, moderate: 46, severe: 82 } as const; // 0.18 / 0.32 of 255
const DASH = [new PathStyleExtension({ dash: true })];

/** Zone marker size grows with score: 4 px at 0, 12 px at 100. */
export const markerRadius = (score: number) => 4 + Math.max(0, Math.min(100, score)) * 0.08;

/** Pure: same input, same layers. Unit-tested without WebGL; MapPage only feeds it data and time. */
export function buildLayers({ districts, zones, signals, hazard, time, pulseIds, onZoneClick }: LayerInput) {
  const [r, g, b] = HAZARDS[hazard].rgb;
  const live = zones.features.filter((f) => f.properties.status !== "watch");
  const watch = zones.features.filter((f) => f.properties.status === "watch");
  const breath = 0.5 + 0.5 * Math.sin(time * 2.2);
  const pick = (info: PickingInfo<Feature<ZoneProps>>) => {
    if (info.object && onZoneClick) onZoneClick(info.object);
  };

  return [
    new GeoJsonLayer<DistrictProps>({
      id: "districts",
      data: districts.features as never,
      filled: true,
      stroked: true,
      getFillColor: (f: { properties: DistrictProps }): RGBA => [r, g, b, BAND_ALPHA[f.properties.band] ?? 0],
      getLineColor: [255, 245, 230, 18],
      lineWidthMinPixels: 0.5,
      updateTriggers: { getFillColor: hazard },
    }),
    new GeoJsonLayer<ZoneProps>({
      id: "zones-watch",
      data: watch as never,
      filled: true,
      getFillColor: [r, g, b, 22],
      getLineColor: [r, g, b, 170],
      lineWidthMinPixels: 1.25,
      getDashArray: [4, 3],
      dashJustified: true,
      extensions: DASH,
      pickable: true,
      onClick: pick,
      updateTriggers: { getFillColor: hazard, getLineColor: hazard },
    } as never),
    new GeoJsonLayer<ZoneProps>({
      id: "zones-active",
      data: live as never,
      filled: true,
      getFillColor: [r, g, b, 40 + Math.round(breath * 30)],
      getLineColor: [r, g, b, 235],
      lineWidthMinPixels: 1.5 + breath * 1.5,
      pickable: true,
      onClick: pick,
      updateTriggers: { getFillColor: [hazard, breath], getLineColor: hazard },
    }),
    new ScatterplotLayer<Feature<ZoneProps>>({
      id: "zone-markers",
      data: live.filter((f) => f.properties.centroid),
      getPosition: (f) => f.properties.centroid!,
      getRadius: (f) => markerRadius(f.properties.score),
      radiusUnits: "pixels",
      stroked: true,
      getFillColor: [r, g, b, 235],
      getLineColor: [r, g, b, 90],
      lineWidthUnits: "pixels",
      getLineWidth: 6 + breath * 4,
      pickable: true,
      onClick: pick,
      updateTriggers: { getFillColor: hazard, getLineColor: hazard, getLineWidth: breath },
    }),
    new ScatterplotLayer<Feature<SignalProps>>({
      id: "signals",
      data: signals.features,
      getPosition: (f) => (f.geometry?.coordinates as [number, number]) ?? [0, 0],
      getRadius: (f) => (pulseIds.has(f.properties.id) ? 9 : 2.5 + (f.properties.severity ?? 1) * 0.6),
      radiusUnits: "pixels",
      getFillColor: (f): RGBA => [r, g, b, pulseIds.has(f.properties.id) ? 255 : 150],
      stroked: false,
      updateTriggers: { getRadius: [...pulseIds], getFillColor: [hazard, ...pulseIds] },
    }),
  ];
}
