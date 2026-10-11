import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { apiGet } from "@/lib/api/client";
import type { Brief, Plan } from "@/lib/api/types";
import { useMe } from "@/lib/hooks/session";

const PAD = "mx-auto max-w-4xl px-4 py-8 md:px-8";

/** Relief officers' review queue: drafted briefs waiting for approval. */
export function BriefsPage() {
  const me = useMe();
  const officer = me.data?.role === "gov_admin";
  const queue = useQuery({ queryKey: ["brief-queue"], queryFn: ({ signal }) => apiGet<Brief[]>("/briefs", undefined, signal), enabled: officer });
  const plans = useQuery({ queryKey: ["plan-queue"], queryFn: ({ signal }) => apiGet<Plan[]>("/plans", undefined, signal), enabled: officer });
  if (me.isPending) return <div className={PAD}><SkeletonRows rows={4} /></div>;
  if (!me.data) return <Navigate to="/login?next=/briefs" replace />;
  if (!officer) return <p className={`${PAD} text-[13px] text-text-2`}>The review queue is for relief officers.</p>;
  if (queue.isPending) return <div className={PAD}><SkeletonRows rows={4} /></div>;
  if (queue.isError) return <div className={PAD}><ErrorState error={queue.error} onRetry={() => queue.refetch()} /></div>;
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4 px-4 py-6 md:px-8 md:py-8">
      <h1 className="font-display text-[34px] text-text">Waiting for your review</h1>
      <h2 className="text-[15px] font-medium text-text">Relief briefs</h2>
      {queue.data.length === 0 ? (
        <EmptyState title="Nothing to review" body="Open a zone and draft a relief brief; drafts wait here for approval." />
      ) : (
        <ul className="flex flex-col gap-3">
          {queue.data.map((b) => (
            <li key={b.id}>
              <Link to={`/zones/${b.zone_id}`} className="flex flex-col gap-2 rounded-[8px] border hairline bg-surface p-4 hover:bg-raised">
                <span className="text-[15px] font-medium text-text">{b.zone_name} <span className="text-[12px] text-text-3">v{b.version}</span></span>
                <span className="text-[13px] text-text-2">{b.summary}</span>
                <span className="num text-[12px] text-text-3">
                  {(b.need_per_day ?? 0).toLocaleString("en-IN")} kL a day · ₹{Math.round(b.budget_inr ?? 0).toLocaleString("en-IN")} for {b.duration_days} days
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <h2 className="text-[15px] font-medium text-text">Long-term plans</h2>
      {(plans.data ?? []).length === 0 ? (
        <p className="text-[13px] text-text-3">No plans waiting.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {(plans.data ?? []).map((p) => (
            <li key={p.id}>
              <Link to={`/zones/${p.zone_id}`} className="flex flex-col gap-1 rounded-[8px] border hairline bg-surface p-4 hover:bg-raised">
                <span className="text-[15px] font-medium text-text">{p.title}</span>
                <span className="num text-[12px] text-text-3">{p.zone_name} · ₹{Math.round(p.total_cost_inr ?? 0).toLocaleString("en-IN")} (indicative)</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
