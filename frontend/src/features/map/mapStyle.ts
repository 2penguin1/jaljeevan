import type { StyleSpecification } from "maplibre-gl";

const CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const CARTO_LIGHT = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

type Palette = { url: string; canvas: string; land: string; water: string; waterway: string; line: string; label: string; horizon: string };
const DARK: Palette = { url: CARTO_DARK, canvas: "#0b0a09", land: "#15130f", water: "#090d10", waterway: "#16222a",
  line: "#24211d", label: "#8a857e", horizon: "#1b1916" };
const LIGHT: Palette = { url: CARTO_LIGHT, canvas: "#f4f6f4", land: "#eef1ec", water: "#c9dde8", waterway: "#a9c9dc",
  line: "#d3d9d4", label: "#58605c", horizon: "#e2e8e4" };

// Hidden: borders (our district layer draws India's official outline), and detail that competes with the data.
const HIDE = /^(boundary_|poi_|housenumber|roadname|building|aeroway|tunnel_|bridge_|rail|place_hamlet|place_suburbs|place_villages|watername_lake|waterway_label|park_)/;

const skyFor = (p: Palette) => ({
  "sky-color": p.canvas,
  "horizon-color": p.horizon,
  "fog-color": p.canvas,
  "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 0.5, 5, 0.2, 7, 0],
});

/** True when the page shows the light theme (chosen, or following a light device). */
export function isLightTheme(): boolean {
  const chosen = document.documentElement.dataset.theme;
  if (chosen) return chosen === "light";
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: light)").matches;
}

/** CARTO dark-matter (or positron in the light theme), recoloured to our tokens, on a globe. Falls back to a plain
 *  globe if the CDN fails. */
export async function loadMapStyle(signal?: AbortSignal, light = false): Promise<StyleSpecification> {
  const p = light ? LIGHT : DARK;
  const sky = skyFor(p);
  try {
    const res = await fetch(p.url, { signal });
    if (!res.ok) throw new Error(String(res.status));
    const style = (await res.json()) as StyleSpecification;
    style.layers = style.layers.map((layer) => {
      const l = structuredClone(layer) as typeof layer & { paint?: Record<string, unknown>; layout?: Record<string, unknown> };
      if (HIDE.test(l.id)) return { ...l, layout: { ...l.layout, visibility: "none" } } as typeof layer;
      l.paint = { ...l.paint };
      if (l.type === "background") l.paint["background-color"] = p.canvas;
      else if (l.id === "water" || l.id === "water_shadow") l.paint["fill-color"] = p.water;
      else if (l.type === "fill") l.paint["fill-color"] = p.land;
      else if (l.id === "waterway") l.paint["line-color"] = p.waterway;
      else if (l.type === "line") l.paint["line-color"] = p.line;
      else if (l.type === "symbol") {
        l.paint["text-color"] = p.label;
        l.paint["text-halo-color"] = p.canvas;
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
      layers: [{ id: "background", type: "background", paint: { "background-color": p.canvas } }],
      projection: { type: "globe" },
      sky,
    } as StyleSpecification;
  }
}

export const INDIA_CENTER: [number, number] = [79.5, 22.5];
export const INDIA_BOUNDS: [[number, number], [number, number]] = [[68.1, 6.5], [97.4, 35.7]];
