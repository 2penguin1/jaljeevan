import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { apiGet } from "@/lib/api/client";
import type { Plan } from "@/lib/api/types";
import { APP_NAME } from "@/lib/config";
import { PlanOptions } from "./PlanCard";

/** A one-page, print-friendly version of an approved long-term plan (Ctrl/Cmd+P or the Print button). */
export function PlanPrintPage() {
  const { planId = "" } = useParams();
  const plan = useQuery({ queryKey: ["plan-print", planId], queryFn: ({ signal }) => apiGet<Plan>(`/plans/${planId}`, undefined, signal) });
  if (plan.isPending) return <div className="mx-auto max-w-3xl px-6 py-8"><SkeletonRows rows={6} /></div>;
  if (plan.isError) return <div className="mx-auto max-w-3xl px-6 py-8"><ErrorState error={plan.error} onRetry={() => plan.refetch()} /></div>;
  const p = plan.data;
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-5 bg-canvas px-6 py-8 print:max-w-none print:px-0 print:py-0">
      <div className="flex items-center justify-between print:hidden">
        <span className="text-[12px] text-text-3">One-page plan</span>
        <button type="button" onClick={() => window.print()} className="h-8 rounded-[6px] border hairline px-3 text-[13px] text-text hover:bg-raised">Print</button>
      </div>
      <header className="flex flex-col gap-1">
        <p className="text-[12px] text-text-3">{APP_NAME} · {p.zone_name} · {p.hazard} · plan v{p.version}</p>
        <h1 className="font-display text-[32px] leading-tight text-text">{p.title}</h1>
      </header>
      <section className="flex flex-col gap-2">
        <h2 className="text-[13px] font-medium text-text">The problem</h2>
        <p className="text-[14px] leading-relaxed text-text-2">{p.problem_summary}</p>
        {p.trend.first_score != null && (
          <p className="num text-[12px] text-text-3">{`Zone score moved from ${p.trend.first_score} to ${p.trend.last_score} since ${p.trend.since}.`}</p>
        )}
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-[13px] font-medium text-text">What to build</h2>
        <PlanOptions plan={p} />
      </section>
      <footer className="text-[11px] leading-relaxed text-text-3">
        Quantities use an estimated village count and planning norms; unit costs are indicative assumptions, not official
        rates. {p.written_by === "template" ? "Text from a template." : `Text drafted by AI (${p.written_by}) and approved by a relief officer.`}
      </footer>
    </article>
  );
}
