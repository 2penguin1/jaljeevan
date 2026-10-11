import type { Hazard } from "@/lib/api/types";
import { HAZARDS } from "@/lib/hazards";

export function Legend({ hazard, indicatorLabel, footprint }: { hazard: Hazard; indicatorLabel?: string; footprint?: boolean }) {
  const c = HAZARDS[hazard].color;
  const mix = (pct: number) => `color-mix(in srgb, ${c} ${pct}%, transparent)`;
  return (
    <dl className="glass grid grid-cols-[14px_1fr] items-center gap-x-2.5 gap-y-2 rounded-[8px] border hairline px-3 py-2.5 text-[12px] text-text-2">
      <dt className="h-2.5 w-3.5 rounded-[2px] border-[1.5px]" style={{ borderColor: c, background: mix(25) }} />
      <dd>Active zone, marker grows with its score</dd>
      <dt className="h-2.5 w-3.5 rounded-[2px] border-[1.5px] border-dashed" style={{ borderColor: c }} />
      <dd>Watch: not confirmed yet</dd>
      <dt className="size-2 justify-self-center rounded-full" style={{ background: c }} />
      <dd>Located post, last 48 hours</dd>
      {footprint && (
        <>
          <dt className="flex h-2.5 w-3.5 overflow-hidden rounded-[2px] border border-dashed border-text-2">
            <span className="flex-1" style={{ background: mix(30) }} />
            <span className="flex-1" style={{ background: mix(55) }} />
          </dt>
          <dd>Taluka shading: measured dryness, dashed if officially declared</dd>
        </>
      )}
      {indicatorLabel && !footprint && (
        <>
          <dt className="flex h-2.5 w-3.5 overflow-hidden rounded-[2px]">
            <span className="flex-1" style={{ background: mix(18) }} />
            <span className="flex-1" style={{ background: mix(32) }} />
          </dt>
          <dd>District tint by {indicatorLabel.charAt(0).toLowerCase() + indicatorLabel.slice(1)}</dd>
        </>
      )}
    </dl>
  );
}
