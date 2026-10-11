import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { BUTTON, INPUT, PRIMARY } from "@/features/tenders/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api/client";
import type { Brief } from "@/lib/api/types";
import { useMe } from "@/lib/hooks/session";

const inr = (n: number | null | undefined) => (n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);
const num = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("en-IN"));
const STATUS: Record<string, string> = { draft: "Draft, waiting for approval", approved: "Approved", rejected: "Rejected" };

/** The zone's relief brief. Officers draft (AI words, code numbers), approve (publishes the tender) or reject;
 *  everyone else sees only approved briefs. */
export function BriefCard({ zoneId }: { zoneId: string }) {
  const me = useMe();
  const client = useQueryClient();
  const navigate = useNavigate();
  const officer = me.data?.role === "gov_admin";
  const [notes, setNotes] = useState("");
  const brief = useQuery({
    queryKey: ["brief", zoneId, me.data?.id ?? "public"],
    queryFn: ({ signal }) => apiGet<Brief | null>(`/zones/${zoneId}/brief`, undefined, signal),
    enabled: !me.isPending,
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["brief", zoneId] });
  const draft = useMutation({ mutationFn: () => apiPost<Brief>(`/zones/${zoneId}/briefs`, {}), onSuccess: refresh });
  const approve = useMutation({
    mutationFn: (id: string) => apiPost<{ tender_id: string }>(`/briefs/${id}/approve`, {}),
    onSuccess: ({ tender_id }) => { refresh(); client.invalidateQueries({ queryKey: ["tenders"] }); navigate(`/tenders/${tender_id}`); },
  });
  const reject = useMutation({ mutationFn: (id: string) => apiPost<void>(`/briefs/${id}/reject`, { notes }), onSuccess: refresh });
  const error = draft.error ?? approve.error ?? reject.error;

  if (brief.isPending) return null;
  const b = brief.data;
  if (!b && !officer) return null;

  return (
    <section aria-label="Relief brief" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[13px] font-medium text-text">Relief brief</h3>
        {b && <span className="text-[12px] text-text-2">v{b.version} · {STATUS[b.status] ?? b.status}</span>}
      </div>
      {!b || (officer && b.status === "rejected") ? (
        <>
          {b?.review_notes && <p className="text-[12px] text-text-3">Last brief rejected: {b.review_notes}</p>}
          <p className="text-[12px] text-text-2">The AI writes the situation from this zone's evidence; every number is computed in code.</p>
          <button type="button" className={PRIMARY} disabled={draft.isPending} onClick={() => draft.mutate()}>
            {draft.isPending ? "Drafting…" : "Draft a relief brief"}
          </button>
        </>
      ) : (
        <>
          <p className="text-[13px] leading-relaxed text-text">{b.summary}</p>
          <ul className="flex list-disc flex-col gap-1 pl-4 text-[13px] text-text-2">
            {b.actions.map((a) => <li key={a.key}>{a.text}</li>)}
          </ul>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t hairline pt-3 text-[12px]">
            <dt className="text-text-2">People on tankers</dt><dd className="num text-right text-text">{num(b.people)}</dd>
            <dt className="text-text-2">Water a day</dt><dd className="num text-right text-text">{num(b.need_per_day)} kL</dd>
            <dt className="text-text-2">Tanker trips a day</dt><dd className="num text-right text-text">{num(b.units_per_day)}</dd>
            <dt className="text-text-2">Price (nearby median)</dt><dd className="num text-right text-text">{inr(b.suggested_price_per_unit)}/kL</dd>
            <dt className="text-text-2">{b.duration_days ?? 30}-day budget</dt><dd className="num text-right text-text">{inr(b.budget_inr)}</dd>
          </dl>
          <p className="text-[11px] leading-relaxed text-text-3">
            {b.written_by === "template" ? "Template words (AI unavailable)" : `Words by AI (${b.written_by})`}; numbers computed in code: {b.formula}
            {b.cited_signal_ids.length > 0 && `; cites ${b.cited_signal_ids.length} post${b.cited_signal_ids.length > 1 ? "s" : ""} from this zone`}.
          </p>
          {officer && b.status === "approved" && (
            <button type="button" className={BUTTON} disabled={draft.isPending} onClick={() => draft.mutate()}>Draft a new version</button>
          )}
          {officer && b.status === "draft" && (
            <div className="flex flex-col gap-2 border-t hairline pt-3">
              <button type="button" className={PRIMARY} disabled={approve.isPending} onClick={() => approve.mutate(b.id)}>Approve and publish tender</button>
              <div className="flex gap-2">
                <label className="sr-only" htmlFor="reject-notes">Reason for rejecting</label>
                <input id="reject-notes" className={INPUT} placeholder="Reason for rejecting" value={notes} maxLength={500}
                  onChange={(e) => setNotes(e.target.value)} />
                <button type="button" className={BUTTON} disabled={reject.isPending} onClick={() => reject.mutate(b.id)}>Reject</button>
              </div>
            </div>
          )}
        </>
      )}
      {error && <p role="alert" className="text-[12px] text-heat">{error instanceof ApiError ? error.detail : "That did not work."}</p>}
    </section>
  );
}
