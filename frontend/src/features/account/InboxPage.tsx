import { Link, Navigate } from "react-router";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import type { InboxBid } from "@/lib/api/types";
import { useMe } from "@/lib/hooks/session";
import { useInbox } from "@/lib/hooks/tenders";

const BUCKETS: { key: "needs_action" | "waiting" | "closed"; title: string; empty: string }[] = [
  { key: "needs_action", title: "Needs your answer", empty: "Nothing waiting for you." },
  { key: "waiting", title: "Waiting for the government", empty: "No open offers with the government." },
  { key: "closed", title: "Closed", empty: "No agreed or declined bids yet." },
];

const PAD = "mx-auto max-w-4xl px-4 py-8 md:px-8";

/** A vendor's tenders, sorted by whose move it is ("needs your action / waiting / closed", as in the reference CRM). */
export function InboxPage() {
  const me = useMe();
  const inbox = useInbox(me.data?.role === "vendor");
  if (me.isPending) return <div className={PAD}><SkeletonRows rows={4} /></div>;
  if (!me.data) return <Navigate to="/login?next=/inbox" replace />;
  if (me.data.role !== "vendor") return <p className={`${PAD} text-[13px] text-text-2`}>The inbox is for tanker vendor accounts.</p>;
  if (inbox.isPending) return <div className={PAD}><SkeletonRows rows={4} /></div>;
  if (inbox.isError) return <div className={PAD}><ErrorState error={inbox.error} onRetry={() => inbox.refetch()} /></div>;
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
      <h1 className="font-display text-[34px] text-text">{me.data.org_name ?? "Your"} inbox</h1>
      {BUCKETS.map(({ key, title, empty }) => (
        <section key={key} aria-label={title} className="flex flex-col gap-2">
          <h2 className="text-[13px] font-medium text-text">
            {title} <span className="num text-text-3">{inbox.data[key].length}</span>
          </h2>
          {inbox.data[key].length === 0
            ? <p className="text-[13px] text-text-3">{empty}</p>
            : inbox.data[key].map((b) => <InboxRow key={b.id} bid={b} />)}
        </section>
      ))}
    </div>
  );
}

function InboxRow({ bid }: { bid: InboxBid }) {
  return (
    <Link to={`/tenders/${bid.tender_id}`}
      className="flex flex-wrap items-baseline justify-between gap-2 rounded-[8px] border hairline bg-surface p-4 hover:bg-raised">
      <span className="text-[14px] text-text">{bid.zone_name}</span>
      {bid.offer && (
        <span className="num text-[12px] text-text-2">
          v{bid.offer.version}: {bid.offer.qty_per_day.toLocaleString("en-IN")} kL a day at ₹{bid.offer.price_per_unit}/kL for {bid.duration_days} days
        </span>
      )}
    </Link>
  );
}
