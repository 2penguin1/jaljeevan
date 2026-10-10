import { useMemo } from "react";
import { useSearchParams } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { ErrorState } from "@/components/patterns/ErrorState";
import type { DistrictProps, FeatureCollection, Hazard, SignalProps, ZoneProps } from "@/lib/api/types";
import { HAZARDS, isHazard } from "@/lib/hazards";
import { useMapDistricts, useMapSignals, useMapZones } from "@/lib/hooks/queries";
import { useAnimationTime, usePrefersReducedMotion } from "@/lib/motion";
import { GlobeMap } from "./GlobeMap";
import { HazardSwitch } from "./HazardSwitch";
import { Legend } from "./Legend";
import { buildLayers } from "./layers";

const EMPTY = { type: "FeatureCollection", features: [] } as const;

export function MapPage() {
  const [params, setParams] = useSearchParams();
  const hazard: Hazard = isHazard(params.get("hazard")) ? (params.get("hazard") as Hazard) : "drought";
  const setHazard = (h: Hazard) => setParams((p) => (p.set("hazard", h), p), { replace: true });

  const zones = useMapZones(hazard);
  const districts = useMapDistricts(hazard);
  const signals = useMapSignals(hazard);
  const reduced = usePrefersReducedMotion();
  const time = useAnimationTime(!reduced);

  const zoneData = (zones.data ?? EMPTY) as FeatureCollection<ZoneProps>;
  const layers = useMemo(
    () =>
      buildLayers({
        districts: (districts.data ?? EMPTY) as FeatureCollection<DistrictProps>,
        zones: zoneData,
        signals: (signals.data ?? EMPTY) as FeatureCollection<SignalProps>,
        hazard,
        time,
        pulseIds: new Set(),
      }),
    [districts.data, zoneData, signals.data, hazard, time],
  );

  const active = zoneData.features.filter((f) => f.properties.status !== "watch").length;
  const watch = zoneData.features.length - active;
  const label = HAZARDS[hazard].label.toLowerCase();

  return (
    <div className="absolute inset-0 overflow-hidden">
      <GlobeMap layers={layers} zoneCount={zoneData.features.length} />
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
      <div className="absolute bottom-6 left-4 hidden md:left-6 md:block">
        <Legend hazard={hazard} indicatorLabel={districts.data?.features[0]?.properties.indicator_label} />
      </div>
    </div>
  );
}
