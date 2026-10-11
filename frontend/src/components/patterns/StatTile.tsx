import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/format";

/** A number with its label. `accent` (a CSS colour, usually a hazard token) tints the top edge and the icon chip. */
export function StatTile({ label, value, hint, className, accent, icon: Icon }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
  accent?: string;
  icon?: LucideIcon;
}) {
  return (
    <div className={cn("relative flex flex-col gap-2 overflow-hidden rounded-[10px] border hairline bg-surface px-4 py-3.5", className)}>
      {accent && <span aria-hidden className="absolute inset-x-0 top-0 h-[3px]" style={{ background: accent }} />}
      <span className="flex items-center gap-2 text-[12px] text-text-2">
        {Icon && (
          <span aria-hidden className="grid h-6 w-6 place-items-center rounded-full"
            style={{ background: accent ? `color-mix(in srgb, ${accent} 16%, transparent)` : undefined, color: accent }}>
            <Icon size={13} strokeWidth={2} />
          </span>
        )}
        {label}
      </span>
      <span className="num text-[28px] leading-none text-text">{value}</span>
      {hint && <span className="text-[12px] text-text-3">{hint}</span>}
    </div>
  );
}
