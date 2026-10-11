import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { ApiError } from "@/lib/api/client";
import type { BidOut, Me } from "@/lib/api/types";
import { ROLE_NAME, useMe } from "@/lib/hooks/session";
import { type BidAction, useBidAction, useRaisePrice, useTender } from "@/lib/hooks/tenders";
import { BUTTON, CommittedBar, Field, INPUT, PRIMARY } from "./ui";

const STATUS: Record<string, string> = { invited: "Invited", countered: "Negotiating", accepted: "Agreed", declined: "Declined" };
const when = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const errorText = (err: unknown) => (err instanceof ApiError ? err.detail : "That did not work. Try again.");

/** Which side the logged-in account plays on a bid: the officer for the government, a vendor only on its own bid. */
function sideOf(me: Me | null | undefined, bid: BidOut): "gov" | "vendor" | null {
  if (me?.role === "gov_admin") return "gov";
  if (me?.role === "vendor" && me.org_id === bid.vendor_id) return "vendor";
  return null;
}

export function TenderPage() {
  const { tenderId = "" } = useParams();
  const tender = useTender(tenderId);
  const me = useMe();

  if (tender.isPending) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><SkeletonRows rows={6} /></div>;
  if (tender.isError) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><ErrorState error={tender.error} onRetry={() => tender.refetch()} /></div>;
  const t = tender.data;
  const officer = me.data?.role === "gov_admin";
  const mine = me.data?.role === "vendor" ? t.bids.filter((b) => b.vendor_id === me.data?.org_id) : t.bids;

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
      <p className="rounded-[8px] border hairline bg-surface px-4 py-3 text-[13px] text-text-2">
        {me.data
          ? `Signed in as ${me.data.name} (${ROLE_NAME[me.data.role] ?? me.data.role}${me.data.org_name ? `, ${me.data.org_name}` : ""}).`
          : <>Anyone can follow this tender. <Link to="/login" className="underline hover:text-text">Log in</Link> as the relief officer or an invited vendor to take part.</>}
      </p>
      {officer && t.bids.some((b) => b.status === "invited" || b.status === "countered") && <RaisePrice tenderId={t.id} current={t.price_per_unit} />}
      <section aria-label="Invited vendors" className="flex flex-col gap-3">
        {t.bids.length === 0 && <p className="text-[13px] text-text-3">No vendor is in reach. Widen the radius in a new tender.</p>}
        {me.data?.role === "vendor" && mine.length === 0 && <p className="text-[13px] text-text-3">Your company was not invited to this tender.</p>}
        {(me.data?.role === "vendor" ? mine : t.bids).map((b) => (
          <BidCard key={b.id} bid={b} rank={t.bids.indexOf(b) + 1} tenderId={t.id} side={sideOf(me.data, b)} />
        ))}
      </section>
    </article>
  );
}

function RaisePrice({ tenderId, current }: { tenderId: string; current: number }) {
  const raise = useRaisePrice(tenderId);
  const [price, setPrice] = useState(current + 5);
  return (
    <form className="flex flex-wrap items-end gap-3 rounded-[8px] border hairline bg-surface p-4"
      onSubmit={(e) => { e.preventDefault(); raise.mutate(price); }}>
      <Field label="New price for every open bid (₹/kL)">
        <input type="number" min={current + 1} className={INPUT} value={price} onChange={(e) => setPrice(Number(e.target.value))} />
      </Field>
      <button type="submit" className={BUTTON} disabled={raise.isPending}>Raise price</button>
      {raise.error && <p role="alert" className="text-[12px] text-heat">{errorText(raise.error)}</p>}
    </form>
  );
}

function BidCard({ bid, rank, tenderId, side }: { bid: BidOut; rank: number; tenderId: string; side: "gov" | "vendor" | null }) {
  const act = useBidAction(tenderId);
  const [countering, setCountering] = useState(false);
  const [price, setPrice] = useState(bid.offer?.price_per_unit ?? 0);
  const [qty, setQty] = useState(bid.offer?.qty_per_day ?? 0);
  const [message, setMessage] = useState("");
  const open = bid.status === "invited" || bid.status === "countered";
  const myTurn = side !== null && open && bid.turn === side;
  const send = (action: BidAction) => act.mutate({ bidId: bid.id, action });

  return (
    <article aria-label={bid.vendor_name} className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[15px] font-medium text-text"><span className="num text-text-3">{rank}.</span> {bid.vendor_name}</h2>
        <span className={bid.status === "accepted" ? "text-[12px] text-success" : "text-[12px] text-text-2"}>
          {STATUS[bid.status] ?? bid.status}{open && ` · waiting for ${bid.turn === "gov" ? "the government" : "the vendor"}`}
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
          <button type="button" className={PRIMARY} disabled={act.isPending} onClick={() => send({ action: "accept", expected_version: bid.version })}>Accept offer</button>
          <button type="button" className={BUTTON} disabled={act.isPending} onClick={() => setCountering(true)}>Counter</button>
          <button type="button" className={BUTTON} disabled={act.isPending} onClick={() => send({ action: "decline", expected_version: bid.version })}>Decline</button>
        </div>
      )}
      {myTurn && countering && (
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => {
          e.preventDefault();
          send({ action: "counter", expected_version: bid.version, price_per_unit: price, qty_per_day: qty });
          setCountering(false);
        }}>
          <Field label="₹/kL"><input type="number" min={1} className={INPUT} value={price} onChange={(e) => setPrice(Number(e.target.value))} /></Field>
          <Field label="kL a day"><input type="number" min={1} className={INPUT} value={qty} onChange={(e) => setQty(Number(e.target.value))} /></Field>
          <button type="submit" className={PRIMARY}>Send counter</button>
          <button type="button" className={BUTTON} onClick={() => setCountering(false)}>Cancel</button>
        </form>
      )}
      {act.error && <p role="alert" className="text-[12px] text-heat">{errorText(act.error)}</p>}
      <ol className="flex flex-col gap-1 border-t hairline pt-2 text-[12px] text-text-3">
        {bid.messages.map((m, i) => (
          <li key={i} className={m.side === "system" ? "" : "text-text-2"}>
            <span className="num">{when.format(new Date(m.at))}</span>{" "}
            {m.author && <span className="text-text">{m.author}: </span>}{m.body}
          </li>
        ))}
      </ol>
      {side && (
        <form className="flex gap-2" onSubmit={(e) => {
          e.preventDefault();
          if (message.trim()) { send({ action: "message", body: message.trim() }); setMessage(""); }
        }}>
          <label className="sr-only" htmlFor={`msg-${bid.id}`}>Message to the other side</label>
          <input id={`msg-${bid.id}`} className={INPUT} placeholder="Write a message" value={message} maxLength={1000}
            onChange={(e) => setMessage(e.target.value)} />
          <button type="submit" className={BUTTON} disabled={act.isPending}>Send</button>
        </form>
      )}
    </article>
  );
}
