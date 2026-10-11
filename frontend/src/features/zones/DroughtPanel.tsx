import { ExternalLink } from "lucide-react";
import type { DroughtPanel as Panel } from "@/lib/api/types";
import { formatPeople, safeUrl } from "@/lib/format";

const LEVEL: Record<string, string> = { none: "Not in drought", watch: "Watch", moderate: "Moderate", severe: "Severe" };
const day = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** SPI / anomaly in plain words (the manual's bands): how unusual the dryness is. */
export function dryness(v: number | null | undefined): string {
  if (v == null) return "No data";
  if (v <= -2) return "Extremely dry";
  if (v <= -1.5) return "Severely dry";
  if (v <= -1) return "Moderately dry";
  if (v < 1) return "Near normal";
  return "Wetter than normal";
}

const signed = (v: number) => (v < 0 ? `−${Math.abs(v).toFixed(1)}` : `+${v.toFixed(1)}`);

function Measure({ label, value, words, note }: { label: string; value: number | null | undefined; words: string; note?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-[12px] text-text-2">{label}</dt>
      <dd className="flex items-baseline gap-2">
        <span className="num text-[18px] text-text">{value == null ? "—" : signed(value)}</span>
        <span className="text-[12px] text-text-2">{words}</span>
      </dd>
      {note && <dd className="text-[11.5px] text-text-3">{note}</dd>}
    </div>
  );
}

/** The measured data behind a drought zone. Plain DOM (no chart library), so the zone page stays light. */
export function DroughtPanel({ panel }: { panel: Panel }) {
  const href = safeUrl(panel.declared?.source_url);
  return (
    <section aria-label="Measured drought data" className="flex flex-col gap-4 rounded-[8px] border hairline bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[13px] font-medium text-text">Measured drought data</h3>
        <span className="text-[12px] text-text-2">Level: <span className="text-text">{LEVEL[panel.level] ?? panel.level}</span></span>
      </div>
      {panel.stale && (
        <p role="note" className="rounded-[6px] border border-drought/40 px-3 py-2 text-[12.5px] text-text">
          Rainfall data is out of date{panel.spi_period ? ` (last update covers to ${day.format(new Date(`${panel.spi_period}T00:00:00`))})` : ""}.
          The level below is held until fresh data arrives.
        </p>
      )}
      <dl className="grid grid-cols-2 gap-4">
        <Measure label="Rain, last 3 months (SPI)" value={panel.spi_18p} words={dryness(panel.spi_18p)}
          note={panel.spi_period ? `to ${day.format(new Date(`${panel.spi_period}T00:00:00`))}` : undefined} />
        <Measure label="Rain, last month (SPI)" value={panel.spi_6p} words={dryness(panel.spi_6p)} />
        <Measure label="Soil moisture anomaly" value={panel.soil_anomaly} words={dryness(panel.soil_anomaly)}
          note={panel.soil_period ? `to ${day.format(new Date(`${panel.soil_period}T00:00:00`))}` : undefined} />
        <div className="flex flex-col gap-1">
          <dt className="text-[12px] text-text-2">People in the dry parts</dt>
          <dd className="num text-[18px] text-text">{formatPeople(panel.people_in_dry_areas)}</dd>
          {panel.people_in_dry_areas != null && panel.people_in_dry_areas_urban != null && (
            <dd className="text-[11.5px] text-text-3">
              {formatPeople(panel.people_in_dry_areas - panel.people_in_dry_areas_urban)} in rural areas
            </dd>
          )}
        </div>
      </dl>
      {panel.declared && (
        <p className="text-[13px] text-text">
          Declared {panel.declared.severity} drought by the state on {day.format(new Date(`${panel.declared.declared_on}T00:00:00`))}
          {panel.declared.order_ref ? ` (${panel.declared.order_ref})` : ""}
          {href && (
            <a href={href} target="_blank" rel="noreferrer noopener" className="ml-2 inline-flex items-center gap-1 text-text-2 hover:text-text">
              Order <ExternalLink size={12} aria-hidden />
            </a>
          )}
        </p>
      )}
      {panel.imd_district_departure_pct != null && (
        <p className="text-[12px] text-text-2">
          IMD district rainfall since the season began: <span className="num text-text">{Math.round(panel.imd_district_departure_pct)}%</span>
          {" "}vs normal{panel.imd_deficient ? ", deficient" : ""} (cross-check)
        </p>
      )}
      {panel.reasons.length > 0 && (
        <ul className="flex list-disc flex-col gap-1 pl-4 text-[12.5px] text-text-2">
          {panel.reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
      <p className="border-t hairline pt-3 text-[11.5px] leading-relaxed text-text-3">{panel.label}. SPI and the soil anomaly compare against each place's own normal; −1 and below is drier than usual.</p>
    </section>
  );
}
