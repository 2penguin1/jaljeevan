import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { BUTTON, INPUT, PRIMARY } from "@/features/tenders/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api/client";
import type { Plan } from "@/lib/api/types";
import { useMe } from "@/lib/hooks/session";

export const inr = (n: number | null | undefined) => (n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);
const STATUS: Record<string, string> = { draft: "Draft, waiting for approval", approved: "Approved", rejected: "Rejected" };

export function PlanOptions({ plan }: { plan: Plan }) {
  return (
    <table className="w-full text-[12px]">
      <caption className="sr-only">Plan options and costs</caption>
      <thead><tr className="text-left text-text-3"><th className="py-1 font-normal">Option</th><th className="py-1 text-right font-normal">Qty</th><th className="py-1 text-right font-normal">Cost</th></tr></thead>
      <tbody>
        {plan.options.map((o) => (
          <tr key={o.key} className="border-t hairline align-top">
            <td className="py-1.5 pr-2 text-text">{o.label}<span className="block text-[11px] text-text-3">{o.basis}</span></td>
            <td className="num py-1.5 text-right text-text-2">{o.quantity.toLocaleString("en-IN")} {o.unit}</td>
            <td className="num py-1.5 text-right text-text">{inr(o.cost_inr)}</td>
          </tr>
        ))}
        <tr className="border-t hairline"><td className="py-1.5 font-medium text-text">Total (indicative)</td><td /><td className="num py-1.5 text-right font-medium text-text">{inr(plan.total_cost_inr)}</td></tr>
      </tbody>
    </table>
  );
}

/** The zone's long-term plan: officers draft / approve / reject; everyone sees approved plans. */
export function PlanCard({ zoneId }: { zoneId: string }) {
  const me = useMe();
  const client = useQueryClient();
  const officer = me.data?.role === "gov_admin";
  const [notes, setNotes] = useState("");
  const plan = useQuery({
    queryKey: ["plan", zoneId, me.data?.id ?? "public"],
    queryFn: ({ signal }) => apiGet<Plan | null>(`/zones/${zoneId}/plan`, undefined, signal),
    enabled: !me.isPending,
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["plan", zoneId] });
  const draft = useMutation({ mutationFn: () => apiPost<Plan>(`/zones/${zoneId}/plans`, {}), onSuccess: refresh });
  const approve = useMutation({ mutationFn: (id: string) => apiPost<void>(`/plans/${id}/approve`, {}), onSuccess: refresh });
  const reject = useMutation({ mutationFn: (id: string) => apiPost<void>(`/plans/${id}/reject`, { notes }), onSuccess: refresh });
  const error = draft.error ?? approve.error ?? reject.error;

  if (plan.isPending) return null;
  const p = plan.data;
  if (!p && !officer) return null;
  return (
    <section aria-label="Long-term plan" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[13px] font-medium text-text">Long-term plan</h3>
        {p && <span className="text-[12px] text-text-2">v{p.version} · {STATUS[p.status] ?? p.status}</span>}
      </div>
      {!p || (officer && p.status === "rejected") ? (
        <>
          {p?.review_notes && <p className="text-[12px] text-text-3">Last plan rejected: {p.review_notes}</p>}
          <p className="text-[12px] text-text-2">Options come from a fixed menu; quantities and costs are computed in code (indicative).</p>
          <button type="button" className={PRIMARY} disabled={draft.isPending} onClick={() => draft.mutate()}>
            {draft.isPending ? "Drafting…" : "Draft a long-term plan"}
          </button>
        </>
      ) : (
        <>
          <p className="text-[14px] font-medium text-text">{p.title}</p>
          <p className="text-[13px] leading-relaxed text-text-2">{p.problem_summary}</p>
          <PlanOptions plan={p} />
          <p className="text-[11px] text-text-3">
            {p.written_by === "template" ? "Template words (AI unavailable)" : `Words by AI (${p.written_by})`}; quantities and costs from code, using indicative planning norms.
          </p>
          {p.status === "approved" && <Link to={`/plans/${p.id}/print`} className={BUTTON}>Print one-pager</Link>}
          {officer && p.status === "approved" && (
            <button type="button" className={BUTTON} disabled={draft.isPending} onClick={() => draft.mutate()}>Draft a new version</button>
          )}
          {officer && p.status === "draft" && (
            <div className="flex flex-col gap-2 border-t hairline pt-3">
              <button type="button" className={PRIMARY} disabled={approve.isPending} onClick={() => approve.mutate(p.id)}>Approve plan</button>
              <div className="flex gap-2">
                <label className="sr-only" htmlFor="plan-reject-notes">Reason for rejecting</label>
                <input id="plan-reject-notes" className={INPUT} placeholder="Reason for rejecting" value={notes} maxLength={500} onChange={(e) => setNotes(e.target.value)} />
                <button type="button" className={BUTTON} disabled={reject.isPending} onClick={() => reject.mutate(p.id)}>Reject</button>
              </div>
            </div>
          )}
        </>
      )}
      {error && <p role="alert" className="text-[12px] text-heat">{error instanceof ApiError ? error.detail : "That did not work."}</p>}
    </section>
  );
}
