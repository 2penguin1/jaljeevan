import { Component, Suspense, lazy, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router";
import type { Feature, ZoneProps } from "@/lib/api/types";
import { APP_NAME } from "@/lib/config";
import { cn, formatInt, formatPeople } from "@/lib/format";
import { HAZARD_LIST } from "@/lib/hazards";
import { mapZonesQuery, useStats } from "@/lib/hooks/queries";
import { useQueries } from "@tanstack/react-query";
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
  const results = useQueries({ queries: HAZARD_LIST.map(mapZonesQuery) });
  const data = results.map((r) => r.data);
  return useMemo(() => {
    const all: Feature<ZoneProps>[] = data.flatMap((fc) => fc?.features ?? []);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, data);
}

function Figure({ value, label, className }: { value: string; label: string; className?: string }) {
  return (
    <dl className={cn("flex flex-col gap-2", className)}>
      <dt className="order-2 max-w-[24ch] text-[15px] leading-snug text-text-2">{label}</dt>
      <dd className="order-1 font-display text-[64px] leading-[0.9] tracking-[-0.02em] text-text [font-variant-numeric:lining-nums_tabular-nums] md:text-[104px]">{value}</dd>
    </dl>
  );
}

const AUDIENCES = [
  { title: "For the relief officer", color: "var(--drought)",
    body: "See which talukas are dry today and why, and how much drinking water their families need. Draft a brief, approve it, and the nearest tanker owners get the request in the same minute." },
  { title: "For tanker owners", color: "var(--flood)",
    body: "Tenders near your depot arrive in your inbox. Answer with your own price, counter when diesel goes up, and see exactly what was agreed. No chasing anyone on the phone." },
  { title: "For NGOs and neighbours", color: "var(--success)",
    body: "Raise support for a village, ask for hands at a water point, or simply tell us your tap has been dry for nine days. It all lands on the same map the officer is looking at." },
];

export function LandingPage() {
  const stats = useStats();
  const { embers, hotspot } = useEmbers();
  const reduced = usePrefersReducedMotion();
  const [webgl] = useState(hasWebGL);
  const [lite] = useState(isLite);
  const [ready, setReady] = useState(false);
  const s = stats.data;

  return (
    <div className="force-dark relative bg-canvas text-[16px] text-text">
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
        </section>
        <section aria-labelledby="why-title" className="relative bg-canvas/95 px-5 py-24 backdrop-blur-sm md:px-10">
          <div className="mx-auto flex max-w-6xl flex-col gap-14">
            <div className="flex max-w-[62ch] flex-col gap-5">
              <h2 id="why-title" className="font-display text-[40px] leading-[1.05] md:text-[56px]">
                Every summer, someone builds the tanker list by hand.
              </h2>
              <p className="text-[17px] leading-relaxed text-text-2">
                Phone calls from sarpanches, WhatsApp forwards, a line in the morning paper, a government order typed in Marathi.
                By the time it is all on one sheet, the wells have been dry for a week. {APP_NAME} does that reading every few
                hours, for the whole country, and puts it on one map.
              </p>
            </div>
            <div className="grid gap-10 md:grid-cols-3">
              {AUDIENCES.map((a) => (
                <div key={a.title} className="flex flex-col gap-3 border-t pt-5" style={{ borderColor: a.color }}>
                  <h3 className="text-[15px] font-medium text-text">{a.title}</h3>
                  <p className="text-[15px] leading-relaxed text-text-2">{a.body}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-4 border-t hairline pt-8 md:flex-row md:items-end md:justify-between">
              <p className="max-w-[70ch] text-[14px] leading-relaxed text-text-2">
                Rain comes from CHIRPS satellite data, soil moisture from Copernicus, drought orders straight from state
                government PDFs, and population from WorldPop. The AI writes sentences. Every number on this site is
                arithmetic you can open and check.
              </p>
              <div className="flex shrink-0 gap-3">
                <Link to="/zones" className="inline-flex h-11 items-center rounded-full bg-text px-6 text-[14px] font-medium text-canvas hover:opacity-90">See the worst-hit zones</Link>
                <Link to="/login" className="inline-flex h-11 items-center rounded-full border border-hairline-strong px-6 text-[14px] text-text hover:bg-raised">Log in</Link>
              </div>
            </div>
          </div>
          <p className="mx-auto mt-16 max-w-6xl text-[12px] leading-relaxed text-text-3">
            Relief from AWS Open Data Terrain Tiles. Rivers from Natural Earth. India&rsquo;s outline from official district boundaries.
          </p>
        </section>
      </main>
    </div>
  );
}
