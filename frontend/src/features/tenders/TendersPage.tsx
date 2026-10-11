import { ClipboardList, Droplets, Hourglass, Truck } from "lucide-react";
import { Link } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { PageHeader } from "@/components/patterns/PageHeader";
import { StatTile } from "@/components/patterns/StatTile";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { useTenders } from "@/lib/hooks/tenders";
import { CommittedBar } from "./ui";

export function TendersPage() {
  const tenders = useTenders();
  if (tenders.isPending) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><SkeletonRows rows={5} /></div>;
  if (tenders.isError) return <div className="mx-auto max-w-5xl px-4 py-8 md:px-8"><ErrorState error={tenders.error} onRetry={() => tenders.refetch()} /></div>;
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-6 md:px-8 md:py-8">
      <PageHeader title="Water tanker tenders" lead="A relief officer asks for drinking water; the nearest reliable tanker owners answer with their price. Offers stay private between the officer and each vendor.">
        <StatTile label="Open tenders" value={tenders.data.filter((t) => t.status === "published").length} accent="var(--flood)" icon={ClipboardList} />
        <StatTile label="Water asked for" value={`${Math.round(tenders.data.reduce((a, t) => a + t.qty_per_day, 0)).toLocaleString("en-IN")} kL`} accent="var(--water)" icon={Droplets} hint="a day, across all tenders" />
        <StatTile label="Water committed" value={`${Math.round(tenders.data.reduce((a, t) => a + t.committed_kl_per_day, 0)).toLocaleString("en-IN")} kL`} accent="var(--success)" icon={Truck} hint="a day, agreed with vendors" />
        <StatTile label="Waiting for the government" value={tenders.data.reduce((a, t) => a + (t.waiting_for_gov ?? 0), 0)} accent="var(--drought)" icon={Hourglass} hint="vendor answers to review" />
      </PageHeader>
      {tenders.data.length === 0 ? (
        <EmptyState title="No tenders yet" body="Open a drought zone and use “Create tanker tender” to ask nearby vendors for water." />
      ) : (
        <ul className="flex flex-col gap-3">
          {tenders.data.map((t) => (
            <li key={t.id}>
              <Link to={`/tenders/${t.id}`} style={{ borderLeftColor: "var(--flood)" }}
                className="flex flex-col gap-3 rounded-[10px] border border-l-[3px] hairline bg-surface p-4 transition-colors hover:bg-raised">
                <span className="text-[15px] font-medium text-text">{t.zone_name}</span>
                <span className="text-[12px] text-text-2">
                  {t.qty_per_day.toLocaleString("en-IN")} kL a day for {t.duration_days} days at ₹{t.price_per_unit}/kL
                </span>
                <CommittedBar committed={t.committed_kl_per_day} needed={t.qty_per_day} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
