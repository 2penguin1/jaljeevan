import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/format";

export type SegmentOption<T extends string> = { value: T; label: string; icon?: LucideIcon; color?: string };

/** A small set of mutually exclusive filters, as pressed/unpressed buttons. */
export function Segmented<T extends string>({ label, value, options, onChange, className }: {
  label: string;
  value: T;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cn("inline-flex max-w-full overflow-x-auto rounded-[8px] border hairline bg-surface p-1", className)}>
      {options.map(({ value: v, label: text, icon: Icon, color }) => {
        const active = v === value;
        return (
          <button
            key={v}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(v)}
            className={cn(
              "inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[13px] transition-colors duration-[var(--dur-1)]",
              active ? "bg-raised text-text" : "text-text-2 hover:text-text",
            )}
          >
            {Icon && <Icon size={13} aria-hidden style={{ color: active ? color : undefined }} />}
            {text}
          </button>
        );
      })}
    </div>
  );
}
