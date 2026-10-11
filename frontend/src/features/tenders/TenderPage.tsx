import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { ApiError } from "@/lib/api/client";
import type { BidOut } from "@/lib/api/types";
import { getDemoCode } from "@/lib/demoCode";
import { type BidAction, useBidAction, useTender } from "@/lib/hooks/tenders";
import { BUTTON, CommittedBar, DemoCodeField, Field, INPUT, PRIMARY } from "./ui";

const STATUS: Record<string, string> = { invited: "Invited", countered: "Negotiating", accepted: "Agreed", declined: "Declined" };
const when = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export function TenderPage() {
  const { tenderId = "" } = useParams();
  const tender = useTender(tenderId);
  const [viewer, setViewer] = useState("gov"); // "gov" or a vendor id: one person plays both sides in the demo

  if (tender.isPending) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><SkeletonRows rows={6} /></div>;
  if (tender.isError) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><ErrorState error={tender.error} onRetry={() => tender.refetch()} /></div>;
  const t = tender.data;

  return (
    <article className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
      <Link to="/tenders" className="inline-flex items-center gap-1.5 text-[13px] text-text-2 hover:text-text">
        <ArrowLeft size={14} aria-hidden /> All tenders
      </Link>
      <header className="flex flex-col gap-4">
        <p className="text-[13px] text-text-2">Water tanker tender, demo vendors</p>
        <h1 className="font-display text-[34px] leading-tight text-text md:text-[44px]">
          <Link to={`/zones/${t.zone_id}`} className="hover:underline">{t.zone_name}</Link>
        </h1>
        <p className="text-[13px] text-text-2">
          {t.qty_per_day.toLocaleString("en-IN")} kL a day for {t.duration_days} days at ₹{t.price_per_unit}/kL, vendors within {t.radius_km} km
        </p>
        <CommittedBar committed={t.committed_kl_per_day} needed={t.qty_per_day} />
      </header>
      <div className="flex flex-wrap items-end gap-4 rounded-[8px] border hairline bg-surface p-4">
        <Field label="Viewing as">
          <select value={viewer} onChange={(e) => setViewer(e.target.value)}
            className="h-8 rounded-[6px] border hairline bg-canvas px-2 text-[13px] text-text">
            <option value="gov">Government relief officer</option>
            {t.bids.map((b) => <option key={b.vendor_id} value={b.vendor_id}>{b.vendor_name}</option>)}
          </select>
        </Field>
        <div className="min-w-[220px] flex-1"><DemoCodeField /></div>
      </div>
      <section aria-label="Invited vendors" className="flex flex-col gap-3">
        {t.bids.length === 0 && <p className="text-[13px] text-text-3">No vendor is in reach. Widen the radius in a new tender.</p>}
        {t.bids.map((b, i) => <BidCard key={b.id} bid={b} rank={i + 1} tenderId={t.id} viewer={viewer} />)}
      </section>
    </article>
  );
}

function BidCard({ bid, rank, tenderId, viewer }: { bid: BidOut; rank: number; tenderId: string; viewer: string }) {
  const act = useBidAction(tenderId);
  const [countering, setCountering] = useState(false);
  const [price, setPrice] = useState(bid.offer?.price_per_unit ?? 0);
  const [qty, setQty] = useState(bid.offer?.qty_per_day ?? 0);
  const side = viewer === "gov" ? "gov" : viewer === bid.vendor_id ? "vendor" : null;
  const myTurn = side !== null && bid.turn === side;
  const send = (action: BidAction) => act.mutate({ bidId: bid.id, action, code: getDemoCode() });

  return (
    <article aria-label={bid.vendor_name} className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[15px] font-medium text-text"><span className="num text-text-3">{rank}.</span> {bid.vendor_name}</h2>
        <span className={bid.status === "accepted" ? "text-[12px] text-success" : "text-[12px] text-text-2"}>
          {STATUS[bid.status] ?? bid.status}{bid.turn !== "none" && ` · waiting for ${bid.turn === "gov" ? "government" : "vendor"}`}
        </span>
      </div>
      <p className="text-[12px] text-text-3">Why invited: {bid.reason}</p>
      {bid.offer && (
        <p className="text-[13px] text-text">
          Offer v{bid.offer.version}: <span className="num">{bid.offer.qty_per_day.toLocaleString("en-IN")}</span> kL a day at{" "}
          <span className="num">₹{bid.offer.price_per_unit}</span>/kL, from the {bid.offer.proposed_by_side === "gov" ? "government" : "vendor"}
          {bid.offer.note && <span className="text-text-2"> “{bid.offer.note}”</span>}
        </p>
      )}
      {myTurn && !countering && (
        <div className="flex flex-wrap gap-2">
          <button type="button" className={PRIMARY} disabled={act.isPending} onClick={() => send({ side, action: "accept" })}>Accept offer</button>
          <button type="button" className={BUTTON} disabled={act.isPending} onClick={() => setCountering(true)}>Counter</button>
          <button type="button" className={BUTTON} disabled={act.isPending} onClick={() => send({ side, action: "decline" })}>Decline</button>
        </div>
      )}
      {myTurn && countering && (
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => {
          e.preventDefault();
          send({ side, action: "counter", price_per_unit: price, qty_per_day: qty });
          setCountering(false);
        }}>
          <Field label="₹/kL"><input type="number" min={1} className={INPUT} value={price} onChange={(e) => setPrice(Number(e.target.value))} /></Field>
          <Field label="kL a day"><input type="number" min={1} className={INPUT} value={qty} onChange={(e) => setQty(Number(e.target.value))} /></Field>
          <button type="submit" className={PRIMARY}>Send counter</button>
          <button type="button" className={BUTTON} onClick={() => setCountering(false)}>Cancel</button>
        </form>
      )}
      {act.error && <p role="alert" className="text-[12px] text-heat">{(act.error as ApiError).detail ?? "That did not work."}</p>}
      <ol className="flex flex-col gap-1 border-t hairline pt-2 text-[12px] text-text-3">
        {bid.messages.map((m, i) => <li key={i}><span className="num">{when.format(new Date(m.at))}</span> {m.body}</li>)}
      </ol>
    </article>
  );
}
