import type { Hazard } from "@/lib/api/types";
import { cn } from "@/lib/format";
import { HAZARDS } from "@/lib/hazards";

export function ScoreMeter({ score, hazard, size = "md", className }: {
  score: number;
  hazard?: Hazard;
  size?: "sm" | "md";
  className?: string;
}) {
  const value = Math.max(0, Math.min(100, score));
  const color = hazard ? HAZARDS[hazard].color : "var(--text)";
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        role="meter"
        aria-label="Zone score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
        className={cn("relative flex-1 overflow-hidden rounded-full bg-raised", size === "sm" ? "h-1" : "h-1.5")}
      >
        <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${value}%`, background: color }} />
        {/* activation threshold: zones go live at 60 */}
        <div className="absolute inset-y-0 w-px bg-text-3" style={{ left: "60%" }} aria-hidden />
      </div>
      <span className={cn("num text-text", size === "sm" ? "w-6 text-[12px]" : "w-8 text-[15px]")}>
        {Math.round(score)}
      </span>
    </div>
  );
}
