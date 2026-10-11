import { Link } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
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
      <h1 className="font-display text-[34px] text-text">Water tanker tenders</h1>
      {tenders.data.length === 0 ? (
        <EmptyState title="No tenders yet" body="Open a drought zone and use “Create tanker tender” to ask nearby vendors for water." />
      ) : (
        <ul className="flex flex-col gap-3">
          {tenders.data.map((t) => (
            <li key={t.id}>
              <Link to={`/tenders/${t.id}`} className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4 hover:bg-raised">
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
