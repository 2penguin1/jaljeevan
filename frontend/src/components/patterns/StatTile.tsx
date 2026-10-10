import type { ReactNode } from "react";
import { cn } from "@/lib/format";

export function StatTile({ label, value, hint, className }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-2 rounded-[6px] border hairline bg-surface px-4 py-3.5", className)}>
      <span className="text-[12px] text-text-2">{label}</span>
      <span className="num text-[26px] leading-none text-text">{value}</span>
      {hint && <span className="text-[12px] text-text-3">{hint}</span>}
    </div>
  );
}
