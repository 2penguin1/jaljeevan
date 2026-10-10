import type { EvidenceItem, Hazard, ScoreBreakdown as Breakdown, ZoneDetail } from "@/lib/api/types";
import { HAZARDS } from "@/lib/hazards";

/** Largest-remainder rounding: whole percentages that always sum to exactly 100. */
export function roundShares(shares: number[]): number[] {
  if (!shares.length) return [];
  const total = shares.reduce((a, b) => a + b, 0) || 1;
  const raw = shares.map((s) => (s / total) * 100);
  const floors = raw.map(Math.floor);
  let left = 100 - floors.reduce((a, b) => a + b, 0);
  const order = raw.map((r, i) => [r - Math.floor(r), i] as const).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  for (const [, i] of order) {
    if (left <= 0) break;
    floors[i] += 1;
    left -= 1;
  }
  return floors;
}

function ruleText(b: Breakdown, indicators: ZoneDetail["indicators"]): string {
  if (!b.rule_met) return "Not confirmed yet: needs two independent sources, an official source, or a weather signal.";
  if (b.independent_sources >= 2) return `Confirmed by ${b.independent_sources} independent sources.`;
  if (b.indicator_boost > 0 && indicators) return `Confirmed by a weather signal: ${indicators.label.toLowerCase()}.`;
  return "Confirmed by an official source.";
}

export function ScoreBreakdown({ breakdown, evidence, indicators, hazard }: {
  breakdown: Breakdown;
  evidence: EvidenceItem[];
  indicators: ZoneDetail["indicators"];
  hazard: Hazard;
}) {
  const color = HAZARDS[hazard].color;
  const pct = roundShares(breakdown.contributions.map((c) => c.share));
  const byId = new Map(evidence.map((e) => [e.signal_id, e]));
  return (
    <section aria-label="How the score adds up" className="flex flex-col gap-4">
      <h3 className="text-[13px] font-medium text-text">How the score adds up</h3>
      {pct.length > 0 && (
        <div className="flex h-2 gap-px overflow-hidden rounded-full" aria-hidden>
          {pct.map((p, i) => (
            <span key={breakdown.contributions[i].signal_id} style={{ width: `${p}%`, background: color, opacity: 1 - i * (0.7 / pct.length) }} />
          ))}
        </div>
      )}
      <ol className="flex flex-col gap-2 text-[13px]">
        {breakdown.contributions.map((c, i) => {
          const e = byId.get(c.signal_id);
          return (
            <li key={c.signal_id} className="flex items-baseline gap-3">
              <span className="num w-10 shrink-0 text-right text-text">{pct[i]}%</span>
              <span className="min-w-0 truncate text-text-2">{e?.domain || e?.source || "Post"}{e?.place ? `, ${e.place}` : ""}</span>
            </li>
          );
        })}
      </ol>
      {indicators && (
        <p className="text-[13px] text-text-2">
          {indicators.label}: <span className="num text-text">{indicators.value ?? "—"}</span>
          {breakdown.indicator_boost > 0 && <> adds <span className="num text-text">+{breakdown.indicator_boost.toFixed(1)}</span> support</>}
        </p>
      )}
      <p className="border-t hairline pt-3 text-[13px] text-text">{ruleText(breakdown, indicators)}</p>
    </section>
  );
}
