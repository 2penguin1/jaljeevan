import type { ReactNode } from "react";

/** The top of an app page: a serif title, one plain sentence, and an optional row of stat tiles. */
export function PageHeader({ title, lead, children }: { title: string; lead: ReactNode; children?: ReactNode }) {
  return (
    <header className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-[38px] leading-[1.05] text-text md:text-[46px]">{title}</h1>
        <p className="max-w-[72ch] text-[14px] leading-relaxed text-text-2">{lead}</p>
      </div>
      {children && <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{children}</div>}
    </header>
  );
}
