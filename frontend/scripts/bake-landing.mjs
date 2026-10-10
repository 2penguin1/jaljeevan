// Bakes the landing page's 3D India from open data. Run from frontend/: `node scripts/bake-landing.mjs`
//
//  - Elevation: AWS Open Data Terrain Tiles (Terrarium PNG, s3://elevation-tiles-prod), zoom 6.
//  - Outline:   our own district boundaries (backend/app/data/seed/india_district.geojson), so the shape is India's.
//  - Rivers:    Natural Earth 1:10m river centre-lines (public domain).
//
// Writes to public/landing/: height.png (sqrt-encoded elevation), normal.webp (smooth shading),
// albedo.webp (stone tones, alpha = India mask), poster.webp (still hillshade shown before WebGL), rivers.json.
import { createCanvas, loadImage } from "@napi-rs/canvas";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

export const BBOX = { lon0: 67.5, lon1: 98.0, lat0: 6.0, lat1: 37.5 }; // keep in sync with src/features/landing/projection.ts
const N = 1024; // output texture size
const Z = 6; // terrain tile zoom
const MAX_M = 7000; // elevation that maps to full height
const CACHE = ".cache/landing";
const OUT = "public/landing";
mkdirSync(CACHE, { recursive: true });
mkdirSync(OUT, { recursive: true });

async function cached(url, file) {
  const path = `${CACHE}/${file}`;
  if (!existsSync(path)) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
    writeFileSync(path, Buffer.from(await res.arrayBuffer()));
  }
  return path;
}

// --- 1. elevation: stitch Terrarium tiles, resample to an equirectangular grid over BBOX ------------------
const world = 256 * 2 ** Z;
const mx = (lon) => ((lon + 180) / 360) * world;
const my = (lat) => {
  const r = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * world;
};
const tx0 = Math.floor(mx(BBOX.lon0) / 256), tx1 = Math.floor(mx(BBOX.lon1) / 256);
const ty0 = Math.floor(my(BBOX.lat1) / 256), ty1 = Math.floor(my(BBOX.lat0) / 256);
const mosaicW = (tx1 - tx0 + 1) * 256, mosaicH = (ty1 - ty0 + 1) * 256;
const mosaic = new Float32Array(mosaicW * mosaicH);
let downloaded = 0;
for (let tx = tx0; tx <= tx1; tx++) {
  for (let ty = ty0; ty <= ty1; ty++) {
    const file = await cached(`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${Z}/${tx}/${ty}.png`, `t${Z}_${tx}_${ty}.png`);
    const img = await loadImage(readFileSync(file));
    const c = createCanvas(256, 256).getContext("2d");
    c.drawImage(img, 0, 0);
    const px = c.getImageData(0, 0, 256, 256).data;
    for (let y = 0; y < 256; y++) {
      for (let x = 0; x < 256; x++) {
        const i = (y * 256 + x) * 4;
        mosaic[((ty - ty0) * 256 + y) * mosaicW + (tx - tx0) * 256 + x] = px[i] * 256 + px[i + 1] + px[i + 2] / 256 - 32768;
      }
    }
    downloaded++;
  }
}
console.log(`terrain: ${downloaded} tiles (zoom ${Z})`);

function elevationAt(lon, lat) {
  const x = mx(lon) - tx0 * 256 - 0.5, y = my(lat) - ty0 * 256 - 0.5;
  const x0 = Math.max(0, Math.min(mosaicW - 2, Math.floor(x))), y0 = Math.max(0, Math.min(mosaicH - 2, Math.floor(y)));
  const fx = x - x0, fy = y - y0;
  const v = (xx, yy) => mosaic[yy * mosaicW + xx];
  return (v(x0, y0) * (1 - fx) + v(x0 + 1, y0) * fx) * (1 - fy) + (v(x0, y0 + 1) * (1 - fx) + v(x0 + 1, y0 + 1) * fx) * fy;
}
const lonAt = (i) => BBOX.lon0 + ((i + 0.5) / N) * (BBOX.lon1 - BBOX.lon0);
const latAt = (j) => BBOX.lat1 - ((j + 0.5) / N) * (BBOX.lat1 - BBOX.lat0);

// --- 2. India mask from our district polygons ------------------------------------------------------------
const districts = JSON.parse(readFileSync("../backend/app/data/seed/india_district.geojson", "utf8"));
const maskCanvas = createCanvas(N, N);
const mctx = maskCanvas.getContext("2d");
mctx.fillStyle = "#fff";
const toPx = ([lon, lat]) => [((lon - BBOX.lon0) / (BBOX.lon1 - BBOX.lon0)) * N, ((BBOX.lat1 - lat) / (BBOX.lat1 - BBOX.lat0)) * N];
for (const f of districts.features) {
  const g = f.geometry;
  if (!g) continue;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
  for (const poly of polys) {
    mctx.beginPath();
    for (const ring of poly) ring.forEach((pt, k) => (k ? mctx.lineTo(...toPx(pt)) : mctx.moveTo(...toPx(pt))));
    mctx.fill("evenodd");
  }
  mctx.lineWidth = 1.5; // close hairline gaps between neighbouring districts
  mctx.strokeStyle = "#fff";
  for (const poly of polys) {
    mctx.beginPath();
    poly[0].forEach((pt, k) => (k ? mctx.lineTo(...toPx(pt)) : mctx.moveTo(...toPx(pt))));
    mctx.stroke();
  }
}
const mask = new Float32Array(N * N);
const mpx = mctx.getImageData(0, 0, N, N).data;
for (let k = 0; k < N * N; k++) mask[k] = mpx[k * 4] / 255;

// --- 3. height, normals, albedo -------------------------------------------------------------------------
const h = new Float32Array(N * N); // displayed height, 0..1 (sqrt keeps detail in the plains)
for (let j = 0; j < N; j++) {
  for (let i = 0; i < N; i++) {
    const e = Math.max(0, Math.min(MAX_M, elevationAt(lonAt(i), latAt(j))));
    h[j * N + i] = Math.sqrt(e / MAX_M); // terrain continues past the border (alpha hides it): no cliff walls
  }
}
// plane size in scene units (see projection.ts): width scaled by cos(mid-latitude)
const midLat = ((BBOX.lat0 + BBOX.lat1) / 2) * (Math.PI / 180);
const planeH = 2, planeW = (planeH * ((BBOX.lon1 - BBOX.lon0) * Math.cos(midLat))) / (BBOX.lat1 - BBOX.lat0);
const DISPLACEMENT = 0.09, RELIEF = 1.8; // shading slightly exaggerated relative to geometry
const dx = planeW / N, dy = planeH / N;
const H = (i, j) => h[Math.max(0, Math.min(N - 1, j)) * N + Math.max(0, Math.min(N - 1, i))] * DISPLACEMENT;

const make = () => createCanvas(N, N);
const heightC = make(), normalC = make(), albedoC = make();
const hImg = heightC.getContext("2d").createImageData(N, N);
const nImg = normalC.getContext("2d").createImageData(N, N);
const aImg = albedoC.getContext("2d").createImageData(N, N);
const STONE = [[0, [38, 34, 30]], [0.18, [56, 50, 43]], [0.45, [104, 93, 79]], [0.75, [150, 138, 120]], [1, [214, 207, 196]]];
const stone = (v) => {
  for (let s = 1; s < STONE.length; s++) {
    if (v <= STONE[s][0]) {
      const [a, ca] = STONE[s - 1], [b, cb] = STONE[s];
      const t = (v - a) / (b - a);
      return ca.map((c, k) => c + (cb[k] - c) * t);
    }
  }
  return STONE.at(-1)[1];
};
const light = (() => { const v = [-0.55, 0.55, 0.62]; const l = Math.hypot(...v); return v.map((x) => x / l); })();
const shade = new Float32Array(N * N);
for (let j = 0; j < N; j++) {
  for (let i = 0; i < N; i++) {
    const k = j * N + i, o = k * 4;
    const gx = ((H(i + 1, j) - H(i - 1, j)) / (2 * dx)) * RELIEF;
    const gy = ((H(i, j - 1) - H(i, j + 1)) / (2 * dy)) * RELIEF; // row j-1 is north (+v)
    const len = Math.hypot(gx, gy, 1);
    const n = [-gx / len, -gy / len, 1 / len];
    shade[k] = Math.max(0, n[0] * light[0] + n[1] * light[1] + n[2] * light[2]);
    const g = Math.round(h[k] * 255);
    hImg.data.set([g, g, g, 255], o);
    nImg.data.set([(n[0] * 0.5 + 0.5) * 255, (n[1] * 0.5 + 0.5) * 255, (n[2] * 0.5 + 0.5) * 255, 255], o);
    const col = stone(h[k]);
    aImg.data.set([col[0], col[1], col[2], Math.round(mask[k] * 255)], o);
  }
}
heightC.getContext("2d").putImageData(hImg, 0, 0);
normalC.getContext("2d").putImageData(nImg, 0, 0);
albedoC.getContext("2d").putImageData(aImg, 0, 0);
writeFileSync(`${OUT}/height.png`, heightC.toBuffer("image/png"));
writeFileSync(`${OUT}/normal.webp`, normalC.toBuffer("image/webp", 90));
writeFileSync(`${OUT}/albedo.webp`, albedoC.toBuffer("image/webp", 90));

// --- 4. poster: a still hillshade of the same relief, shown instantly and to devices without WebGL ------
const PW = 1600, PH = 1000;
const relief = make();
const rImg = relief.getContext("2d").createImageData(N, N);
for (let k = 0; k < N * N; k++) {
  const col = stone(h[k]);
  const s = 0.32 + 0.95 * shade[k];
  rImg.data.set([Math.min(255, col[0] * s), Math.min(255, col[1] * s), Math.min(255, col[2] * s), Math.round(mask[k] * 255)], k * 4);
}
relief.getContext("2d").putImageData(rImg, 0, 0);
const poster = createCanvas(PW, PH);
const pctx = poster.getContext("2d");
pctx.fillStyle = "#0b0a09";
pctx.fillRect(0, 0, PW, PH);
const drawH = PH * 0.9, drawW = drawH * (planeW / planeH);
pctx.drawImage(relief, PW * 0.62 - drawW / 2, (PH - drawH) / 2, drawW, drawH); // India sits right of the headline
writeFileSync(`${OUT}/poster.webp`, poster.toBuffer("image/webp", 76));

// --- 5. rivers: Natural Earth centre-lines inside India, simplified ---------------------------------------
const riversPath = await cached(
  "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_rivers_lake_centerlines.geojson",
  "ne_10m_rivers.geojson",
);
const inIndia = ([lon, lat]) => {
  const [x, y] = toPx([lon, lat]).map(Math.floor);
  return x >= 0 && y >= 0 && x < N && y < N && mask[y * N + x] > 0.5;
};
const rivers = [];
for (const f of JSON.parse(readFileSync(riversPath, "utf8")).features) {
  if ((f.properties?.scalerank ?? 99) > 8 || !f.geometry) continue;
  const lines = f.geometry.type === "LineString" ? [f.geometry.coordinates] : f.geometry.type === "MultiLineString" ? f.geometry.coordinates : [];
  for (const line of lines) {
    let run = [];
    const flush = () => { if (run.length > 2) rivers.push(run); run = []; };
    for (const pt of line) {
      if (!inIndia(pt)) { flush(); continue; }
      const last = run.at(-1);
      if (!last || Math.hypot(pt[0] - last[0], pt[1] - last[1]) > 0.06) run.push([+pt[0].toFixed(3), +pt[1].toFixed(3)]);
    }
    flush();
  }
}
writeFileSync(`${OUT}/rivers.json`, JSON.stringify(rivers));

const size = (f) => `${(readFileSync(`${OUT}/${f}`).length / 1024).toFixed(0)} KB`;
console.log(`plane ${planeW.toFixed(3)} x ${planeH}; rivers ${rivers.length} lines`);
for (const f of ["height.png", "normal.webp", "albedo.webp", "poster.webp", "rivers.json"]) console.log(f, size(f));
