import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import { EvidenceQuote } from "@/components/patterns/EvidenceQuote";
import { HazardBadge } from "@/components/patterns/HazardBadge";
import { ScoreMeter } from "@/components/patterns/ScoreMeter";
import { Skeleton } from "@/components/patterns/Skeleton";
import { Sparkline } from "@/components/patterns/Sparkline";
import { ApiError } from "@/lib/api/client";
import type { Geometry } from "@/lib/api/types";
import { formatInt, formatPeople, timeAgo } from "@/lib/format";
import { HAZARDS } from "@/lib/hazards";
import { useZone } from "@/lib/hooks/queries";
import { BriefCard } from "@/features/briefs/BriefCard";
import { ZoneCommunity } from "@/features/community/ZoneCommunity";
import { ReliefNeedCard } from "@/features/tenders/ReliefNeedCard";
import { DroughtPanel } from "./DroughtPanel";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { TrendChart } from "./TrendChart";
import { TREND, ZONE_TYPE } from "./labels";
import { ZoneMiniMap } from "./ZoneMiniMap";

const POPULATION_LABEL: Record<string, string> = {
  worldpop: "People living in the zone area",
  worldpop_dry_areas: "People in the dry parts",
};

const backLink = (
  <Link to="/zones" className="inline-flex items-center gap-1.5 text-[13px] text-text-2 hover:text-text">
    <ArrowLeft size={14} aria-hidden /> All zones
  </Link>
);

export function ZonePage() {
  const { zoneId } = useParams();
  const query = useZone(zoneId);

  if (query.isError) {
    const missing = query.error instanceof ApiError && (query.error.status === 404 || query.error.status === 422);
    return (
      <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
        {missing ? (
          <EmptyState
            title="Zone not found"
            body="It may have been resolved or merged into a nearby zone, or the link is incomplete."
            action={<Link to="/zones" className="rounded-[6px] border hairline px-3 py-2 text-[13px] hover:bg-raised">Back to all zones</Link>}
          />
        ) : (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        )}
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div role="status" aria-label="Loading zone" className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-8 md:px-8">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-12 w-2/3" />
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const { zone, evidence, score_breakdown, trend, indicators } = query.data;
  const color = HAZARDS[zone.hazard].color;

  return (
    <article className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-6 md:px-8 md:py-8">
      <header className="flex flex-col gap-6">
        {backLink}
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="flex min-w-0 flex-col gap-3">
            <h1 className="font-display text-[40px] leading-[1.05] text-text md:text-[52px]">{zone.name}</h1>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px] text-text-2">
              <HazardBadge hazard={zone.hazard} status={zone.status} />
              <span>{ZONE_TYPE[zone.zone_type] ?? zone.zone_type}</span>
              {zone.district && zone.zone_type !== "district_wide" && <span>{zone.district} district</span>}
              <span>Last evidence {timeAgo(zone.last_seen)}</span>
            </div>
          </div>
          <ZoneMiniMap geometry={zone.geometry as Geometry | null} color={color} label={`Outline of ${zone.name}`} />
        </div>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[8px] border hairline bg-[var(--hairline)] md:grid-cols-4">
          <div className="col-span-2 bg-canvas p-4 md:col-span-1">
            <dt className="text-[12px] text-text-2">Score</dt>
            <dd className="mt-2"><ScoreMeter score={zone.score} hazard={zone.hazard} /></dd>
          </div>
          <div className="bg-canvas p-4">
            <dt className="text-[12px] text-text-2">
              {POPULATION_LABEL[zone.population_source ?? ""] ?? "People in the zone"}
            </dt>
            <dd className="num mt-2 text-[22px] leading-none text-text">{formatPeople(zone.population_est)}</dd>
            {zone.population_urban != null && zone.population_est != null && (
              <dd className="mt-1.5 text-[12px] text-text-3">
                {formatInt(zone.population_urban)} urban, {formatInt(zone.population_est - zone.population_urban)} rural
              </dd>
            )}
          </div>
          <div className="bg-canvas p-4">
            <dt className="text-[12px] text-text-2">Independent sources</dt>
            <dd className="num mt-2 text-[22px] leading-none text-text">{zone.independent_sources}</dd>
          </div>
          <div className="col-span-2 flex items-end justify-between gap-3 bg-canvas p-4 md:col-span-1">
            <div>
              <dt className="text-[12px] text-text-2">Trend</dt>
              <dd className="mt-2 text-[15px] text-text">{TREND[zone.trend] ?? zone.trend}</dd>
            </div>
            <Sparkline values={trend.map((t) => t.score)} color={color} />
          </div>
        </dl>
      </header>

      <section aria-labelledby="why-title" className="flex flex-col gap-5">
        <h2 id="why-title" className="font-display text-[28px] text-text">Why this zone</h2>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex flex-col gap-3">
            {evidence.length === 0 ? (
              <EmptyState className="py-4" title="No posts linked yet" body="This zone rests on measured data so far; posts from the area will appear here." />
            ) : (
              evidence.map((e) => (
                <EvidenceQuote key={e.signal_id} quote={e.quote} title={e.title} summary={e.summary} domain={e.domain}
                  source={e.source} credibility={e.credibility} url={e.url} publishedAt={e.published_at} place={e.place}
                  weight={e.weight} />
              ))
            )}
          </div>
          <aside className="flex flex-col gap-8">
            <BriefCard zoneId={zone.id} />
            {(zone.hazard === "drought" || zone.hazard === "water") && <ReliefNeedCard zoneId={zone.id} />}
            {query.data.drought && <DroughtPanel panel={query.data.drought} />}
            <ScoreBreakdown breakdown={score_breakdown} evidence={evidence} indicators={indicators} hazard={zone.hazard} />
            <section aria-label="Score over time" className="flex flex-col gap-3">
              <h3 className="text-[13px] font-medium text-text">Score over time</h3>
              <TrendChart points={trend} color={color} />
            </section>
          </aside>
        </div>
      </section>
      <ZoneCommunity zoneId={zone.id} />
    </article>
  );
}
