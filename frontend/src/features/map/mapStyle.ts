import type { StyleSpecification } from "maplibre-gl";

const CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const CANVAS = "#0b0a09";
const LAND = "#15130f";
const WATER = "#090d10";
const LINE = "#24211d";
const LABEL = "#8a857e";

// Hidden: borders (our district layer draws India's official outline), and detail that competes with the data.
const HIDE = /^(boundary_|poi_|housenumber|roadname|building|aeroway|tunnel_|bridge_|rail|place_hamlet|place_suburbs|place_villages|watername_lake|waterway_label|park_)/;

const sky = {
  "sky-color": CANVAS,
  "horizon-color": "#1b1916",
  "fog-color": CANVAS,
  "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 0.5, 5, 0.2, 7, 0],
};

/** CARTO dark-matter, recoloured to our tokens, on a globe. Falls back to a plain globe if the CDN fails. */
export async function loadMapStyle(signal?: AbortSignal): Promise<StyleSpecification> {
  try {
    const res = await fetch(CARTO_DARK, { signal });
    if (!res.ok) throw new Error(String(res.status));
    const style = (await res.json()) as StyleSpecification;
    style.layers = style.layers.map((layer) => {
      const l = structuredClone(layer) as typeof layer & { paint?: Record<string, unknown>; layout?: Record<string, unknown> };
      if (HIDE.test(l.id)) return { ...l, layout: { ...l.layout, visibility: "none" } } as typeof layer;
      l.paint = { ...l.paint };
      if (l.type === "background") l.paint["background-color"] = CANVAS;
      else if (l.id === "water" || l.id === "water_shadow") l.paint["fill-color"] = WATER;
      else if (l.type === "fill") l.paint["fill-color"] = LAND;
      else if (l.id === "waterway") l.paint["line-color"] = "#16222a";
      else if (l.type === "line") l.paint["line-color"] = LINE;
      else if (l.type === "symbol") {
        l.paint["text-color"] = LABEL;
        l.paint["text-halo-color"] = CANVAS;
        l.paint["text-halo-width"] = 1.2;
      }
      return l;
    });
    return { ...style, projection: { type: "globe" }, sky } as StyleSpecification;
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    return {
      version: 8,
      sources: {},
      layers: [{ id: "background", type: "background", paint: { "background-color": CANVAS } }],
      projection: { type: "globe" },
      sky,
    } as StyleSpecification;
  }
}

export const INDIA_CENTER: [number, number] = [79.5, 22.5];
export const INDIA_BOUNDS: [[number, number], [number, number]] = [[68.1, 6.5], [97.4, 35.7]];
