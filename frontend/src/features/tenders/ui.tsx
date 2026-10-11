import type { ReactNode } from "react";

export const BUTTON = "inline-flex h-8 items-center justify-center gap-1.5 rounded-[6px] border hairline px-3 text-[13px] text-text hover:bg-raised disabled:opacity-50";
export const PRIMARY = "inline-flex h-8 items-center justify-center gap-1.5 rounded-[6px] bg-text px-3 text-[13px] font-medium text-canvas hover:opacity-90 disabled:opacity-50";
export const INPUT = "h-8 w-full rounded-[6px] border hairline bg-canvas px-2 text-[13px] text-text num";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-[12px] text-text-2">
      {label}
      {children}
    </label>
  );
}

export function CommittedBar({ committed, needed }: { committed: number; needed: number }) {
  const share = needed > 0 ? Math.min(1, committed / needed) : 0;
  return (
    <div className="flex flex-col gap-2">
      <div className="h-2 overflow-hidden rounded-full bg-raised" role="progressbar" aria-label="Water committed"
        aria-valuemin={0} aria-valuemax={needed} aria-valuenow={committed}>
        <span className="block h-full rounded-full bg-drought" style={{ width: `${share * 100}%` }} />
      </div>
      <p className="num text-[13px] text-text-2">
        {`${committed.toLocaleString("en-IN")} of ${needed.toLocaleString("en-IN")} kL a day committed (${Math.round(share * 100)}%)`}
      </p>
    </div>
  );
}
