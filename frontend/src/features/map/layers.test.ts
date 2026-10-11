import type { DistrictProps, Feature, FeatureCollection, FootprintProps, SignalProps, ZoneProps } from "@/lib/api/types";
import { buildLayers, type LayerInput } from "./layers";

const empty = <P>(): FeatureCollection<P> => ({ type: "FeatureCollection", features: [] });
const square = { type: "Polygon", coordinates: [[[77, 12], [78, 12], [78, 13], [77, 13], [77, 12]]] };

function zone(id: string, status: ZoneProps["status"], score: number): Feature<ZoneProps> {
  return {
    type: "Feature", id, geometry: square,
    properties: { name: id, hazard: "drought", zone_type: "rural", status, score, trend: "new",
      population_est: 1000, independent_sources: 2, centroid: [77.5, 12.5] },
  };
}
const signal = (id: string): Feature<SignalProps> => ({
  type: "Feature", id, geometry: { type: "Point", coordinates: [77.5, 12.5] },
  properties: { id, severity: 3, source: "rss", title: "t", published_at: "2026-10-10T00:00:00Z", zone_id: null },
});

const base: LayerInput = {
  districts: empty<DistrictProps>(), zones: empty<ZoneProps>(), signals: empty<SignalProps>(),
  hazard: "drought", time: 0, pulseIds: new Set(),
};
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type LooseLayer = { id: string; props: Record<string, any> };
const byId = (layers: ReturnType<typeof buildLayers>): Record<string, LooseLayer> =>
  Object.fromEntries(layers.map((l) => [l.id, l as unknown as LooseLayer]));

test("empty data still builds every layer without throwing", () => {
  const layers = byId(buildLayers(base));
  expect(Object.keys(layers)).toEqual(["districts", "zones-watch", "zones-active", "zone-markers", "signals"]);
  expect(layers["zones-active"].props.data).toEqual([]);
});

test("watch zones are dashed, active zones solid, score markers only for active", () => {
  const zones = { type: "FeatureCollection" as const, features: [zone("w", "watch", 20), zone("a", "active", 70)] };
  const layers = byId(buildLayers({ ...base, zones }));
  expect((layers["zones-watch"].props.data as Feature<ZoneProps>[]).map((f) => f.id)).toEqual(["w"]);
  expect((layers["zones-active"].props.data as Feature<ZoneProps>[]).map((f) => f.id)).toEqual(["a"]);
  expect(layers["zones-watch"].props.extensions).toHaveLength(1);
  expect(layers["zones-active"].props.extensions ?? []).toHaveLength(0);
  expect((layers["zone-markers"].props.data as Feature<ZoneProps>[]).map((f) => f.id)).toEqual(["a"]);
  const radius = layers["zone-markers"].props.getRadius as (f: Feature<ZoneProps>) => number;
  expect(radius(zone("a", "active", 90))).toBeGreaterThan(radius(zone("a", "active", 60)));
});

test("pulsing signals are drawn larger, in the hazard colour", () => {
  const signals = { type: "FeatureCollection" as const, features: [signal("s1"), signal("s2")] };
  const layer = byId(buildLayers({ ...base, hazard: "flood", signals, pulseIds: new Set(["s2"]) })).signals;
  const radius = layer.props.getRadius as (f: Feature<SignalProps>) => number;
  expect(radius(signal("s2"))).toBeGreaterThan(radius(signal("s1")));
  const color = layer.props.getFillColor as (f: Feature<SignalProps>) => number[];
  expect(color(signal("s1")).slice(0, 3)).toEqual([63, 182, 216]);
});

test("district tint follows the indicator band", () => {
  const d = (band: DistrictProps["band"]): Feature<DistrictProps> => ({
    type: "Feature", id: 1, geometry: square,
    properties: { id: 1, name: "d", state_code: "KA", indicator_value: -50, indicator_label: "x", band },
  });
  const fill = byId(buildLayers(base)).districts.props.getFillColor as (f: Feature<DistrictProps>) => number[];
  expect(fill(d("none"))[3]).toBe(0);
  expect(fill(d("severe"))[3]).toBeGreaterThan(fill(d("moderate"))[3]);
});


test("the drought footprint shades talukas by level and dashes declared ones", () => {
  const taluka = (id: number, level: FootprintProps["level"], declared: boolean) => ({
    type: "Feature" as const, id, geometry: square,
    properties: { id, name: "t", district: "d", level, spi_18p: -2, people: 1, declared },
  });
  const footprint = { type: "FeatureCollection" as const, features: [taluka(1, "severe", false), taluka(2, "moderate", true)] };
  const layers = byId(buildLayers({ ...base, footprint }));
  const fill = layers["footprint"].props.getFillColor as (f: unknown) => number[];
  expect(fill(taluka(1, "severe", false))[3]).toBeGreaterThan(fill(taluka(2, "moderate", true))[3]);
  expect(layers["footprint-declared"].props.data).toHaveLength(1);
  expect(byId(buildLayers(base))["footprint"]).toBeUndefined();
});
