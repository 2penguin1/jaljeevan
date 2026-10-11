import { DataTable, type Column } from "@/components/patterns/DataTable";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import { SkeletonRows } from "@/components/patterns/Skeleton";
import { StatTile } from "@/components/patterns/StatTile";
import type { DeclarationWatchInfo, OpsRun } from "@/lib/api/types";
import { formatInt, formatPeople } from "@/lib/format";
import { useOps, useStats } from "@/lib/hooks/queries";

const REASONS: Record<string, string> = {
  too_old: "Older than 30 days",
  no_keyword: "No water or heat words",
  not_india: "Not about India",
  near_duplicate: "Copy of another story",
  unclear: "AI could not tell",
  irrelevant: "Not about a crisis",
};
const SOURCE_LABEL: Record<string, string> = {
  "chirps-spi": "Rainfall (CHIRPS SPI)",
  "gdo-soil": "Soil moisture (Copernicus GDO)",
};

const reasonLabel = (r: string) => REASONS[r] ?? r.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());

export function providerName(key: string): string {
  if (key.includes("nova-lite")) return "Amazon Nova Lite";
  if (key.includes("nova-pro")) return "Amazon Nova Pro";
  if (key.includes("claude") || key.includes("anthropic")) return "Claude on Bedrock";
  if (key.startsWith("groq:")) return `Groq ${key.split("/").at(-1)}`;
  return key;
}

type Stage = Record<string, unknown> | undefined;
const num = (v: unknown) => (typeof v === "number" ? v : 0);

function runFacts(run: OpsRun) {
  const s = run.stats as Record<string, Stage>;
  const ingest = (s.ingest ?? {}) as Record<string, Stage>;
  const sources = Object.entries(ingest).filter(([k]) => k !== "weather");
  const failed = sources.filter(([, v]) => v && "error" in v).length;
  const stageErrors = ["ingest", "watch", "classify", "geocode", "zones"].filter((k) => s[k] && "error" in (s[k] as object));
  const issues = [
    s.skipped ? "Skipped: another run was in progress" : "",
    failed ? `${failed} source${failed > 1 ? "s" : ""} failed` : "",
    stageErrors.length ? `${stageErrors.join(", ")} failed` : "",
  ].filter(Boolean);
  const seconds = run.finished_at ? (new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000 : null;
  return {
    fetched: sources.reduce((a, [, v]) => a + num(v?.fetched), 0),
    inserted: sources.reduce((a, [, v]) => a + num(v?.inserted), 0),
    classified: num(s.classify?.classified),
    active: num(s.zones?.active),
    duration: seconds === null ? "Running" : seconds >= 60 ? `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s` : `${Math.round(seconds)}s`,
    issues,
  };
}

const when = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

const RUN_COLUMNS: Column<OpsRun>[] = [
  { key: "started", header: "Started", sortValue: (r) => r.started_at, cell: (r) => when.format(new Date(r.started_at)) },
  { key: "duration", header: "Took", cell: (r) => <span className="text-text-2">{runFacts(r).duration}</span> },
  { key: "fetched", header: "Fetched", numeric: true, cell: (r) => formatInt(runFacts(r).fetched) },
  { key: "new", header: "New", numeric: true, cell: (r) => formatInt(runFacts(r).inserted) },
  { key: "classified", header: "Relevant", numeric: true, cell: (r) => formatInt(runFacts(r).classified) },
  { key: "active", header: "Active zones", numeric: true, cell: (r) => formatInt(runFacts(r).active) },
  {
    key: "issues", header: "Issues",
    cell: (r) => {
      const { issues } = runFacts(r);
      return issues.length ? <span className="text-heat">{issues.join("; ")}</span> : <span className="text-text-3">None</span>;
    },
  },
];

function BarList({ rows, label }: { rows: [string, number][]; label: string }) {
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <section aria-label={label} className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <h2 className="text-[13px] font-medium text-text">{label}</h2>
      {rows.length === 0 ? (
        <p className="text-[13px] text-text-3">Nothing yet.</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {rows.map(([name, n]) => (
            <li key={name} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-[13px]">
              <span className="truncate text-text-2">{name}</span>
              <span className="num text-text">{formatInt(n)}</span>
              <span className="col-span-2 h-1 overflow-hidden rounded-full bg-raised">
                <span className="block h-full rounded-full bg-text-2" style={{ width: `${(n / max) * 100}%` }} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// boundary pools: Telangana mandals sit inside the old Andhra Pradesh boundaries
const STATE_NAME: Record<string, string> = {
  KA: "Karnataka", AP: "Andhra Pradesh and Telangana", TN: "Tamil Nadu", GJ: "Gujarat", RJ: "Rajasthan",
  MP: "Madhya Pradesh", CT: "Chhattisgarh", UP: "Uttar Pradesh", KL: "Kerala", HR: "Haryana", PB: "Punjab",
};

function DeclarationWatch({ info }: { info: DeclarationWatchInfo }) {
  const read = Object.values(info.sources).reduce((a, n) => a + n, 0);
  const states = Object.entries(info.declared_by_state).sort((a, b) => b[1] - a[1]);
  return (
    <section aria-label="Declaration watch" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
      <h2 className="text-[13px] font-medium text-text">Declaration watch</h2>
      {info.last_checked === null ? (
        <p className="text-[13px] text-text-3">
          The news watch for state drought declarations has not run yet. It runs with the pipeline, at most once a day.
        </p>
      ) : (
        <>
          <p className="text-[13px] text-text-2">
            {formatInt(read)} articles read this season, last checked {when.format(new Date(info.last_checked))}.{" "}
            {formatInt(info.waiting)} talukas wait for a second news source or a person&rsquo;s check.
          </p>
          {states.length === 0 ? (
            <p className="text-[13px] text-text-3">
              No taluka declared from the news yet. Each one needs an official order, or two independent news sites.
            </p>
          ) : (
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-2 text-[13px]">
              {states.map(([code, n]) => (
                <div key={code} className="contents">
                  <dt className="text-text-2">{STATE_NAME[code] ?? code}</dt>
                  <dd className="num text-right text-text">{formatInt(n)}</dd>
                </div>
              ))}
            </dl>
          )}
        </>
      )}
    </section>
  );
}

export function OpsPage() {
  const ops = useOps();
  const stats = useStats();

  if (ops.isPending) return <div className="mx-auto max-w-6xl px-4 py-8 md:px-8"><SkeletonRows rows={8} /></div>;
  if (ops.isError) return <div className="mx-auto max-w-6xl px-4 py-8 md:px-8"><ErrorState error={ops.error} onRetry={() => ops.refetch()} /></div>;

  const { runs, totals } = ops.data;
  const reasons = Object.entries(totals.rejected_by_reason).map(([r, n]) => [reasonLabel(r), n] as [string, number]);
  const providers = Object.entries(totals.batches_by_provider)
    .map(([p, n]) => [providerName(p), n] as [string, number])
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Posts collected" value={formatInt(totals.signals)} hint="All time, after removing exact copies" />
        <StatTile label="Relevant posts" value={formatInt(totals.classified)} hint="Read by the AI and kept" />
        <StatTile label="Active zones" value={stats.data ? formatInt(stats.data.active_zones) : "—"}
          hint={stats.data ? `${formatInt(stats.data.watch_zones)} more on watch` : undefined} />
        <StatTile label="AI tokens used" value={formatPeople(totals.tokens.input_tokens + totals.tokens.output_tokens)}
          hint={`${formatPeople(totals.tokens.output_tokens)} of them written by the AI`} />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <BarList label="Why posts were set aside" rows={reasons} />
        <BarList label="Batches answered per AI model" rows={providers} />
      </div>
      <section aria-label="Drought data" className="flex flex-col gap-3 rounded-[8px] border hairline bg-surface p-4">
        <h2 className="text-[13px] font-medium text-text">Drought data</h2>
        {(ops.data.indicators ?? []).length === 0 ? (
          <p className="text-[13px] text-text-3">No rainfall or soil data yet. It downloads on the next pipeline run once talukas are loaded.</p>
        ) : (
          <dl className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-6 gap-y-2 text-[13px]">
            {(ops.data.indicators ?? []).map((i) => (
              <div key={i.source} className="contents">
                <dt className="text-text-2">{SOURCE_LABEL[i.source] ?? i.source}</dt>
                <dd className="text-text">to {when.format(new Date(i.period)).split(",")[0]}</dd>
                <dd className="num text-right text-text">{formatInt(i.areas)}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>
      {ops.data.declarations && <DeclarationWatch info={ops.data.declarations} />}
      <section aria-labelledby="runs-title" className="flex flex-col gap-3">
        <h2 id="runs-title" className="text-[13px] font-medium text-text">Recent pipeline runs</h2>
        {runs.length === 0 ? (
          <EmptyState title="No pipeline runs yet" body="Start one with the run_pipeline command; each run collects posts, reads them and updates zones." />
        ) : (
          <div className="overflow-x-auto rounded-[8px] border hairline">
            <DataTable caption="Recent pipeline runs" columns={RUN_COLUMNS} rows={runs} rowKey={(r) => r.id} />
          </div>
        )}
      </section>
    </div>
  );
}
