import type { ReactNode } from "react";
import { cn } from "@/lib/format";

export function EmptyState({ title, body, action, className }: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-start gap-2 px-1 py-10", className)}>
      <h2 className="font-display text-[24px] leading-tight text-text">{title}</h2>
      {body && <p className="max-w-[52ch] text-[13px] leading-relaxed text-text-2">{body}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
