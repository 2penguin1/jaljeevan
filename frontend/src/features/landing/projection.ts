/** Lon/lat -> relief-plane coordinates. Must match scripts/bake-landing.mjs (same BBOX, same plane size). */
export const BBOX = { lon0: 67.5, lon1: 98.0, lat0: 6.0, lat1: 37.5 };

const midLat = (((BBOX.lat0 + BBOX.lat1) / 2) * Math.PI) / 180;
export const PLANE = {
  h: 2,
  w: (2 * (BBOX.lon1 - BBOX.lon0) * Math.cos(midLat)) / (BBOX.lat1 - BBOX.lat0),
};
export const DISPLACEMENT = 0.09; // full-height relief in scene units (bake uses the same value for normals)

/** Returns [x, z]: east is +x, north is -z (away from a camera looking north). */
export function project(lon: number, lat: number): [number, number] {
  const u = (lon - BBOX.lon0) / (BBOX.lon1 - BBOX.lon0);
  const v = (BBOX.lat1 - lat) / (BBOX.lat1 - BBOX.lat0);
  return [(u - 0.5) * PLANE.w, (v - 0.5) * PLANE.h];
}

/** Texture coordinates (0..1, origin top-left) of a lon/lat, for sampling the baked height image. */
export function textureUV(lon: number, lat: number): [number, number] {
  return [(lon - BBOX.lon0) / (BBOX.lon1 - BBOX.lon0), (BBOX.lat1 - lat) / (BBOX.lat1 - BBOX.lat0)];
}
