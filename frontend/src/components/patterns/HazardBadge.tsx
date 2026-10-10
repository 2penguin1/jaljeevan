import type { Hazard } from "@/lib/api/types";
import { cn } from "@/lib/format";
import { HAZARDS, STATUS_LABEL } from "@/lib/hazards";

/** Hazard as icon + word (never colour alone). Watch zones get a dashed outline, live ones a solid tint. */
export function HazardBadge({ hazard, status, className }: { hazard: Hazard; status?: string; className?: string }) {
  const h = HAZARDS[hazard];
  const Icon = h.icon;
  const watch = status === "watch";
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-[6px] border px-2 text-[12px] font-medium leading-none",
        watch ? "border-dashed" : "border-solid",
        className,
      )}
      style={{
        color: h.color,
        borderColor: `color-mix(in srgb, ${h.color} ${watch ? 55 : 30}%, transparent)`,
        background: watch ? "transparent" : `color-mix(in srgb, ${h.color} 12%, transparent)`,
      }}
    >
      <Icon size={13} strokeWidth={2} aria-hidden />
      <span>{h.label}</span>
      {status && <span className="text-text-2">{STATUS_LABEL[status] ?? status}</span>}
    </span>
  );
}
