import type { Hazard } from "@/lib/api/types";
import { cn } from "@/lib/format";
import { HAZARDS, HAZARD_LIST } from "@/lib/hazards";

export function HazardSwitch({ value, onChange }: { value: Hazard; onChange: (h: Hazard) => void }) {
  return (
    <div role="group" aria-label="Hazard" className="glass inline-flex rounded-[8px] border hairline p-1">
      {HAZARD_LIST.map((h) => {
        const { label, icon: Icon, color } = HAZARDS[h];
        const active = h === value;
        return (
          <button
            key={h}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(h)}
            className={cn(
              "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-3 text-[13px] transition-colors duration-[var(--dur-2)]",
              active ? "bg-raised text-text" : "text-text-2 hover:text-text",
            )}
          >
            <Icon size={14} aria-hidden style={{ color: active ? color : undefined }} />
            {label}
          </button>
        );
      })}
    </div>
  );
}
