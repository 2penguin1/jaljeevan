import { Component, Suspense, lazy, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router";
import type { Feature, ZoneProps } from "@/lib/api/types";
import { APP_NAME } from "@/lib/config";
import { cn, formatInt, formatPeople } from "@/lib/format";
import { HAZARD_LIST } from "@/lib/hazards";
import { useMapZones, useStats } from "@/lib/hooks/queries";
import { usePrefersReducedMotion } from "@/lib/motion";
import type { Ember } from "./Scene";

const Scene = lazy(() => import("./Scene"));

/** If WebGL fails mid-way, keep the poster instead of crashing the page. */
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function hasWebGL(): boolean {
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    return false;
  }
}

const isLite = () => window.innerWidth < 768 || (navigator.hardwareConcurrency ?? 8) <= 4;

function useEmbers() {
  const drought = useMapZones("drought");
  const flood = useMapZones("flood");
  const heat = useMapZones("heat");
  return useMemo(() => {
    const all: Feature<ZoneProps>[] = [drought.data, flood.data, heat.data].flatMap((fc) => fc?.features ?? []);
    const embers: Ember[] = all
      .filter((f) => f.properties.centroid)
      .map((f) => ({
        id: String(f.id), lon: f.properties.centroid![0], lat: f.properties.centroid![1],
        hazard: f.properties.hazard, active: f.properties.status !== "watch", score: f.properties.score,
      }))
      .filter((e) => HAZARD_LIST.includes(e.hazard));
    const top = all.filter((f) => f.properties.centroid).sort((a, b) => b.properties.score - a.properties.score)[0];
    const hotspot = top ? { lon: top.properties.centroid![0], lat: top.properties.centroid![1], name: top.properties.name } : null;
    return { embers, hotspot };
  }, [drought.data, flood.data, heat.data]);
}

function Figure({ value, label, className }: { value: string; label: string; className?: string }) {
  return (
    <dl className={cn("flex flex-col gap-2", className)}>
      <dt className="order-2 max-w-[24ch] text-[15px] leading-snug text-text-2">{label}</dt>
      <dd className="order-1 font-display text-[64px] leading-[0.9] tracking-[-0.02em] text-text [font-variant-numeric:lining-nums_tabular-nums] md:text-[104px]">{value}</dd>
    </dl>
  );
}

export function LandingPage() {
  const stats = useStats();
  const { embers, hotspot } = useEmbers();
  const reduced = usePrefersReducedMotion();
  const [webgl] = useState(hasWebGL);
  const [lite] = useState(isLite);
  const [ready, setReady] = useState(false);
  const s = stats.data;

  return (
    <div className="relative bg-canvas text-[16px] text-text">
      <div aria-hidden className="fixed inset-0">
        <img src="/landing/poster.webp" alt="" className="h-full w-full object-cover object-[62%_50%] max-md:object-[60%_85%]" />
        {webgl && (
          <SceneBoundary>
            <Suspense fallback={null}>
              <div className={cn("absolute inset-0 transition-opacity duration-[1200ms] ease-[var(--ease)]", ready ? "opacity-100" : "opacity-0")}>
                <Scene embers={embers} hotspot={hotspot} motion={!reduced} lite={lite} onReady={() => setReady(true)} />
              </div>
            </Suspense>
          </SceneBoundary>
        )}
        {/* keep text legible over the relief */}
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(11,10,9,0.9)_0%,rgba(11,10,9,0.55)_38%,rgba(11,10,9,0)_62%)] max-md:bg-[linear-gradient(180deg,rgba(11,10,9,0.9)_0%,rgba(11,10,9,0.6)_30%,rgba(11,10,9,0)_50%,rgba(11,10,9,0)_68%,rgba(11,10,9,0.85)_100%)]" />
      </div>

      <header className="fixed inset-x-0 top-0 z-20 flex h-16 items-center justify-between px-5 md:px-10">
        <span className="font-display text-[24px] leading-none">{APP_NAME}</span>
        <Link to="/map" className="inline-flex h-10 items-center rounded-full bg-text px-5 text-[14px] font-medium text-canvas transition-colors duration-[var(--dur-2)] hover:bg-white">
          Open the live map
        </Link>
      </header>

      <main className="relative z-10">
        <section className="flex min-h-dvh flex-col justify-start px-5 pb-16 pt-24 md:justify-center md:px-10 md:pt-28">
          <h1 className="max-w-[13ch] font-display text-[52px] leading-[0.98] tracking-[-0.02em] md:text-[96px]">
            See every water crisis in India, as it happens.
          </h1>
          <p className="mt-6 max-w-[44ch] text-[17px] leading-relaxed text-text-2 md:text-[19px]">
            Live signals from news, social media and citizens, turned into verified relief zones.
          </p>
          <Figure className="mt-auto md:mt-14" value={s ? formatInt(s.active_zones) : "—"} label="zones confirmed right now" />
        </section>
        <section className="flex min-h-dvh flex-col justify-end px-5 pb-24 md:justify-center md:px-10">
          <Figure value={s ? formatPeople(s.people_affected) : "—"}
            label={hotspot ? `people live in active zones. The highest score is ${hotspot.name}.` : "people live in active zones"} />
        </section>
        <section className="flex min-h-dvh flex-col justify-end px-5 pb-24 md:px-10">
          <Figure value={s ? formatInt(s.posts_analysed_7d) : "—"} label="posts read and checked in the last seven days" />
          <p className="mt-16 max-w-[70ch] text-[12px] leading-relaxed text-text-3">
            Relief from AWS Open Data Terrain Tiles. Rivers from Natural Earth. India&rsquo;s outline from official district boundaries.
          </p>
        </section>
      </main>
    </div>
  );
}
