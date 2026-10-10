import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Suspense, lazy, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import type { DistrictProps, Feature, FeatureCollection, Hazard, SignalProps, ZoneProps } from "@/lib/api/types";
import { cn } from "@/lib/format";
import { HAZARDS, isHazard } from "@/lib/hazards";
import { useMapDistricts, useMapSignals, useMapZones } from "@/lib/hooks/queries";
import { useLiveSubscription } from "@/lib/live/LiveContext";
import { HazardSwitch } from "./HazardSwitch";
import { Legend } from "./Legend";
import { LiveFeed } from "./LiveFeed";
import { ZonePreview } from "./ZonePreview";
import type { LayerInput } from "./layers";

const GlobeMap = lazy(() => import("./GlobeMap").then((m) => ({ default: m.GlobeMap }))); // WebGL code in its own chunk
const EMPTY = { type: "FeatureCollection", features: [] } as const;
const PULSE_MS = 6000;

/** Ids of posts that just arrived over SSE; each one pulses on the map and in the feed for a few seconds. */
function useFreshSignals() {
  const [fresh, setFresh] = useState<Set<string>>(() => new Set());
  useLiveSubscription((e) => {
    if (e.event !== "signal") return;
    setFresh((s) => new Set(s).add(e.data.id));
    setTimeout(() => setFresh((s) => {
      const next = new Set(s);
      next.delete(e.data.id);
      return next;
    }), PULSE_MS);
  });
  return fresh;
}

export function MapPage() {
  const [params, setParams] = useSearchParams();
  const hazard: Hazard = isHazard(params.get("hazard")) ? (params.get("hazard") as Hazard) : "drought";
  const setHazard = (h: Hazard) => setParams((p) => (p.set("hazard", h), p), { replace: true });

  const zones = useMapZones(hazard);
  const districts = useMapDistricts(hazard);
  const signals = useMapSignals(hazard);
  const fresh = useFreshSignals();
  const [selected, setSelected] = useState<Feature<ZoneProps> | null>(null);
  const [panelOpen, setPanelOpen] = useState(() => window.matchMedia("(min-width: 768px)").matches);
  const selectZone = useCallback((z: Feature<ZoneProps>) => {
    setSelected(z);
    setPanelOpen(true);
  }, []);

  const zoneData = (zones.data ?? EMPTY) as FeatureCollection<ZoneProps>;
  const input = useMemo<Omit<LayerInput, "time">>(
    () => ({
      districts: (districts.data ?? EMPTY) as FeatureCollection<DistrictProps>,
      zones: zoneData,
      signals: (signals.data ?? EMPTY) as FeatureCollection<SignalProps>,
      hazard,
      pulseIds: fresh,
      onZoneClick: selectZone,
    }),
    [districts.data, zoneData, signals.data, hazard, fresh, selectZone],
  );

  const active = zoneData.features.filter((f) => f.properties.status !== "watch").length;
  const watch = zoneData.features.length - active;
  const label = HAZARDS[hazard].label.toLowerCase();

  return (
    <div className="absolute inset-0 overflow-hidden" data-zone-count={zones.isSuccess ? zoneData.features.length : undefined}>
      <Suspense fallback={null}>
        <GlobeMap input={input} />
      </Suspense>
      <div className="pointer-events-none absolute left-4 top-4 flex max-w-[calc(100%-2rem)] flex-col items-start gap-3 md:left-6 md:top-5">
        <div className="pointer-events-auto">
          <HazardSwitch value={hazard} onChange={setHazard} />
        </div>
        {zones.isSuccess && zoneData.features.length > 0 && (
          <p className="glass rounded-[6px] px-2.5 py-1.5 text-[12px] text-text-2">
            <span className="num text-text">{active}</span> active and <span className="num text-text">{watch}</span> on
            watch
          </p>
        )}
        {zones.isError && (
          <ErrorState className="glass pointer-events-auto" error={zones.error} onRetry={() => zones.refetch()} />
        )}
        {zones.isSuccess && zoneData.features.length === 0 && (
          <div className="glass pointer-events-auto rounded-[8px] border hairline px-4">
            <EmptyState
              className="py-4"
              title={`No ${label} zones right now`}
              body="A zone appears when posts from at least two independent sources point at the same place."
            />
          </div>
        )}
      </div>
      <aside
        aria-label="Live feed"
        className={cn(
          "glass absolute inset-x-3 bottom-[4.25rem] top-auto flex max-h-[55%] flex-col overflow-hidden rounded-[8px] border hairline md:inset-x-auto md:right-5 md:top-5 md:w-[340px]",
          selected ? "md:bottom-auto md:max-h-[calc(100%-4rem)]" : "md:bottom-11 md:max-h-none", // preview hugs its content
        )}
        hidden={!panelOpen}
      >
        <div className="flex h-11 shrink-0 items-center justify-between border-b hairline pl-4 pr-2">
          <span className="text-[13px] font-medium text-text">{selected ? "Zone" : "Latest posts"}</span>
          <button type="button" onClick={() => setPanelOpen(false)} aria-label="Hide panel"
            className="grid size-8 place-items-center rounded-[6px] text-text-2 hover:bg-raised hover:text-text">
            <PanelRightClose size={16} aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {selected ? (
            <ZonePreview key={String(selected.id)} zone={selected} onClose={() => setSelected(null)} />
          ) : (
            <LiveFeed freshIds={fresh} />
          )}
        </div>
      </aside>
      {!panelOpen && (
        <button type="button" onClick={() => setPanelOpen(true)} aria-expanded={false}
          className="glass absolute bottom-[4.5rem] right-4 inline-flex h-9 items-center gap-2 rounded-[8px] border hairline px-3 text-[13px] text-text md:bottom-auto md:right-5 md:top-5">
          <PanelRightOpen size={15} aria-hidden /> Latest posts
        </button>
      )}
      <div className="absolute bottom-6 left-4 hidden md:left-6 md:block">
        <Legend hazard={hazard} indicatorLabel={districts.data?.features[0]?.properties.indicator_label} />
      </div>
    </div>
  );
}
