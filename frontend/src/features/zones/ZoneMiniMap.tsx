import type { Geometry } from "@/lib/api/types";

type Ring = [number, number][];

function rings(geometry: Geometry | null | undefined): Ring[] {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return [(geometry.coordinates as Ring[])[0]];
  if (geometry.type === "MultiPolygon") return (geometry.coordinates as Ring[][]).map((p) => p[0]);
  return [];
}

/** SVG path of a zone's outer rings, fitted into a w x h box (equirectangular, longitude scaled by latitude). */
export function outlinePath(geometry: Geometry | null | undefined, w: number, h: number, pad = 6): string {
  const all = rings(geometry).filter((r) => r?.length);
  if (!all.length) return "";
  const pts = all.flat();
  const lat0 = (Math.min(...pts.map((p) => p[1])) + Math.max(...pts.map((p) => p[1]))) / 2;
  const k = Math.cos((lat0 * Math.PI) / 180);
  const xs = pts.map((p) => p[0] * k);
  const ys = pts.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const scale = Math.min((w - pad * 2) / (maxX - minX || 1), (h - pad * 2) / (maxY - minY || 1));
  const offX = (w - (maxX - minX) * scale) / 2;
  const offY = (h - (maxY - minY) * scale) / 2;
  return all
    .map((ring) =>
      ring
        .map(([lon, lat], i) => `${i ? "L" : "M"}${(offX + (lon * k - minX) * scale).toFixed(1)},${(offY + (maxY - lat) * scale).toFixed(1)}`)
        .join("") + "Z",
    )
    .join("");
}

export function ZoneMiniMap({ geometry, color, label }: { geometry: Geometry | null; color: string; label: string }) {
  const d = outlinePath(geometry, 160, 120);
  return (
    <svg viewBox="0 0 160 120" width={160} height={120} role="img" aria-label={label} className="rounded-[6px] border hairline bg-surface">
      <defs>
        <pattern id="mini-grid" width="16" height="16" patternUnits="userSpaceOnUse">
          <path d="M16 0H0V16" fill="none" stroke="var(--hairline)" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width="160" height="120" fill="url(#mini-grid)" />
      {d && <path d={d} fill={color} fillOpacity={0.16} stroke={color} strokeWidth={1.25} strokeLinejoin="round" />}
    </svg>
  );
}
