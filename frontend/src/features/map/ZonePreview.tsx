import { X } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router";
import { HazardBadge } from "@/components/patterns/HazardBadge";
import { ScoreMeter } from "@/components/patterns/ScoreMeter";
import type { Feature, ZoneProps } from "@/lib/api/types";
import { formatPeople } from "@/lib/format";

const TREND: Record<string, string> = { new: "New", escalating: "Escalating", stable: "Stable", easing: "Easing" };
const TYPE: Record<string, string> = { urban_pocket: "Urban pocket", town: "Town", rural: "Rural", district_wide: "Whole district" };

export function ZonePreview({ zone, onClose }: { zone: Feature<ZoneProps>; onClose: () => void }) {
  const z = zone.properties;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <section aria-labelledby="zone-preview-title" className="flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 id="zone-preview-title" className="font-display text-[26px] leading-[1.1] text-text">{z.name}</h2>
        <button type="button" onClick={onClose} aria-label="Close zone preview"
          className="grid size-8 shrink-0 place-items-center rounded-[6px] text-text-2 hover:bg-raised hover:text-text">
          <X size={16} aria-hidden />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <HazardBadge hazard={z.hazard} status={z.status} />
        <span className="text-[12px] text-text-2">{TYPE[z.zone_type] ?? z.zone_type}</span>
      </div>
      <ScoreMeter score={z.score} hazard={z.hazard} />
      <dl className="grid grid-cols-3 gap-3 border-y hairline py-3">
        <div>
          <dt className="text-[11.5px] text-text-3">People</dt>
          <dd className="num mt-1 text-[15px] text-text">{formatPeople(z.population_est)}</dd>
        </div>
        <div>
          <dt className="text-[11.5px] text-text-3">Sources</dt>
          <dd className="num mt-1 text-[15px] text-text">{z.independent_sources}</dd>
        </div>
        <div>
          <dt className="text-[11.5px] text-text-3">Trend</dt>
          <dd className="mt-1 text-[14px] text-text">{TREND[z.trend] ?? z.trend}</dd>
        </div>
      </dl>
      <Link to={`/zones/${zone.id}`}
        className="inline-flex h-9 items-center justify-center rounded-[6px] bg-text px-4 text-[13px] font-medium text-canvas hover:bg-white">
        Open zone
      </Link>
    </section>
  );
}
