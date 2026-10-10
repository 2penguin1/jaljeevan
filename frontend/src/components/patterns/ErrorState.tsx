import { RotateCw } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/format";

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const message = error instanceof ApiError ? error.detail : "Something failed while loading this.";
  return (
    <div role="alert" className={cn("flex flex-wrap items-center gap-3 rounded-[6px] border border-heat/30 px-4 py-3", className)}>
      <span className="text-[13px] text-text">{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry}
          className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-[6px] border hairline px-3 text-[13px] hover:bg-raised">
          <RotateCw size={13} aria-hidden /> Try again
        </button>
      )}
    </div>
  );
}
