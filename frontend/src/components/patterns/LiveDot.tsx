import type { LiveStatus } from "@/lib/live/useLiveEvents";
import { cn } from "@/lib/format";

const LABEL: Record<LiveStatus, string> = { connecting: "Connecting", live: "Live", reconnecting: "Reconnecting" };

export function LiveDot({ status, className }: { status: LiveStatus; className?: string }) {
  const live = status === "live";
  return (
    <span role="status" className={cn("inline-flex items-center gap-2 text-[12px] text-text-2", className)}>
      <span className="relative flex size-2">
        {live && <span className="absolute inset-0 animate-ping rounded-full bg-success opacity-60" />}
        <span className={cn("relative size-2 rounded-full", live ? "bg-success" : "bg-text-3")} />
      </span>
      {LABEL[status]}
    </span>
  );
}
