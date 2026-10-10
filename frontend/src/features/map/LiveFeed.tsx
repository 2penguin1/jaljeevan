import { Link } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import { Skeleton } from "@/components/patterns/Skeleton";
import type { FeedItem } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/format";
import { HAZARDS, isHazard } from "@/lib/hazards";
import { useFeed } from "@/lib/hooks/queries";

function FeedRow({ item, fresh }: { item: FeedItem; fresh: boolean }) {
  const hazard = item.hazards.find(isHazard);
  const color = hazard ? HAZARDS[hazard].color : "var(--text-3)";
  const body = (
    <>
      <span aria-hidden className="my-0.5 w-[3px] shrink-0 self-stretch rounded-full"
        style={{ background: color, opacity: 0.35 + (item.severity ?? 1) * 0.13 }} />
      <span className="min-w-0">
        <span className="line-clamp-2 text-[13px] leading-snug text-text">{item.english_summary || item.title}</span>
        <span className="mt-1 flex flex-wrap gap-x-2 text-[11.5px] text-text-3">
          {item.place && <span className="text-text-2">{item.place}</span>}
          <span>{item.domain || item.source}</span>
          {item.published_at && <time dateTime={item.published_at}>{timeAgo(item.published_at)}</time>}
        </span>
      </span>
    </>
  );
  const cls = cn(
    "flex gap-3 rounded-[6px] px-2 py-2.5 transition-colors duration-[var(--dur-1)]",
    fresh && "animate-[feed-in_var(--dur-3)_var(--ease)]",
  );
  return (
    <li>
      {item.zone_id ? (
        <Link to={`/zones/${item.zone_id}`} className={cn(cls, "hover:bg-raised")}>{body}</Link>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  );
}

/** Newest relevant posts. Live events invalidate the query, so new posts slide in at the top. */
export function LiveFeed({ freshIds = new Set<string>() }: { freshIds?: Set<string> }) {
  const feed = useFeed();
  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];

  if (feed.isPending) {
    return (
      <div role="status" aria-label="Loading posts" className="flex flex-col gap-3 p-3">
        {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12" />)}
      </div>
    );
  }
  if (feed.isError) return <ErrorState className="m-3" error={feed.error} onRetry={() => feed.refetch()} />;
  if (items.length === 0) {
    return <EmptyState className="px-4 py-6" title="No posts yet" body="New posts appear here as soon as they are analysed." />;
  }
  return (
    <div className="p-2">
      <ul className="flex flex-col">
        {items.map((item) => <FeedRow key={item.id} item={item} fresh={freshIds.has(item.id)} />)}
      </ul>
      {feed.hasNextPage && (
        <button type="button" onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}
          className="mt-2 h-9 w-full rounded-[6px] border hairline text-[13px] text-text-2 hover:bg-raised hover:text-text disabled:opacity-50">
          {feed.isFetchingNextPage ? "Loading" : "Show older posts"}
        </button>
      )}
    </div>
  );
}
