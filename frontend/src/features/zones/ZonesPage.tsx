import { AlertTriangle, Eye, Newspaper, Users } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { DataTable, type Column } from "@/components/patterns/DataTable";
import { EmptyState } from "@/components/patterns/EmptyState";
import { PageHeader } from "@/components/patterns/PageHeader";
import { StatTile } from "@/components/patterns/StatTile";
import { ErrorState } from "@/components/patterns/ErrorState";
import { HazardBadge } from "@/components/patterns/HazardBadge";
import { ScoreMeter } from "@/components/patterns/ScoreMeter";
import { Segmented, type SegmentOption } from "@/components/patterns/Segmented";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import type { Hazard, ZoneStatus, ZoneSummary } from "@/lib/api/types";
import { formatInt, formatPeople, timeAgo } from "@/lib/format";
import { HAZARDS, HAZARD_LIST, isHazard } from "@/lib/hazards";
import { useStats, useZones } from "@/lib/hooks/queries";
import { TREND, ZONE_TYPE } from "./labels";

const HAZARD_OPTIONS: SegmentOption<Hazard | "all">[] = [
  { value: "all", label: "All" },
  ...HAZARD_LIST.map((h) => ({ value: h, label: HAZARDS[h].label, icon: HAZARDS[h].icon, color: HAZARDS[h].color })),
];
const STATUS_OPTIONS: SegmentOption<ZoneStatus | "all">[] = [
  { value: "all", label: "Any status" },
  { value: "active", label: "Active" },
  { value: "watch", label: "Watch" },
];

const COLUMNS: Column<ZoneSummary>[] = [
  {
    key: "name", header: "Zone", sortValue: (z) => z.name,
    cell: (z) => (
      <span className="flex flex-col">
        <Link to={`/zones/${z.id}`} className="text-text hover:underline" onClick={(e) => e.stopPropagation()}>{z.name}</Link>
        <span className="text-[12px] text-text-3">{ZONE_TYPE[z.zone_type] ?? z.zone_type}</span>
      </span>
    ),
  },
  { key: "hazard", header: "Hazard", sortValue: (z) => z.hazard, cell: (z) => <HazardBadge hazard={z.hazard} status={z.status} /> },
  { key: "score", header: "Score", numeric: true, sortValue: (z) => z.score, className: "w-40",
    cell: (z) => <ScoreMeter score={z.score} hazard={z.hazard} size="sm" /> },
  { key: "sources", header: "Sources", numeric: true, sortValue: (z) => z.independent_sources, cell: (z) => z.independent_sources },
  { key: "people", header: "People", numeric: true, sortValue: (z) => z.population_est, cell: (z) => formatPeople(z.population_est) },
  { key: "trend", header: "Trend", sortValue: (z) => z.trend, cell: (z) => <span className="text-text-2">{TREND[z.trend] ?? z.trend}</span> },
  { key: "seen", header: "Last evidence", sortValue: (z) => z.last_seen, cell: (z) => <span className="text-text-2">{timeAgo(z.last_seen)}</span> },
];

export function ZonesPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const hazardParam = params.get("hazard");
  const hazard = isHazard(hazardParam) ? hazardParam : undefined;
  const statusParam = params.get("status");
  const status = statusParam === "active" || statusParam === "watch" ? statusParam : undefined;
  const zones = useZones({ hazard, status });

  const setFilter = (key: string, value: string) =>
    setParams((p) => {
      if (value === "all") p.delete(key);
      else p.set(key, value);
      return p;
    });

  const noun = hazard ? `${HAZARDS[hazard].label.toLowerCase()} zones` : "zones";
  const stats = useStats();
  const s = stats.data;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
      <PageHeader title="Where help is needed" lead="Every zone is a taluka or neighbourhood where measured data, official orders or people's own posts point to a water crisis. Highest score first.">
        <StatTile label="Active zones" value={s ? formatInt(s.active_zones) : "—"} accent="var(--heat)" icon={AlertTriangle} hint="Confirmed and needing action" />
        <StatTile label="On watch" value={s ? formatInt(s.watch_zones) : "—"} accent="var(--drought)" icon={Eye} hint="Early signs, not confirmed yet" />
        <StatTile label="People in active zones" value={s ? formatPeople(s.people_affected) : "—"} accent="var(--flood)" icon={Users} hint="Living in the affected parts" />
        <StatTile label="Posts read this week" value={s ? formatInt(s.posts_analysed_7d) : "—"} accent="var(--water)" icon={Newspaper} hint="News, Reddit, X and citizens" />
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Hazard" value={hazard ?? "all"} options={HAZARD_OPTIONS} onChange={(v) => setFilter("hazard", v)} />
        <Segmented label="Status" value={status ?? "all"} options={STATUS_OPTIONS} onChange={(v) => setFilter("status", v)} />
        {zones.data && zones.data.length > 0 && (
          <span className="ml-auto text-[12px] text-text-3">
            <span className="num text-text-2">{zones.data.length}</span> {noun}, highest score first
          </span>
        )}
      </div>
      {zones.isPending && <SkeletonRows rows={8} />}
      {zones.isError && <ErrorState error={zones.error} onRetry={() => zones.refetch()} />}
      {zones.data?.length === 0 && (
        <EmptyState
          title={`No ${noun} right now`}
          body="Zones appear when posts from at least two independent sources, an official source or a weather signal point at the same place."
        />
      )}
      {zones.data && zones.data.length > 0 && (
        <div className="overflow-x-auto rounded-[8px] border hairline bg-canvas">
          <DataTable caption="Zones" columns={COLUMNS} rows={zones.data} rowKey={(z) => z.id}
            onRowClick={(z) => navigate(`/zones/${z.id}`)} />
        </div>
      )}
    </div>
  );
}
