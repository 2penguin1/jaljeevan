import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => typeof window !== "undefined" && window.matchMedia(QUERY).matches);
  useEffect(() => {
    const mq = window.matchMedia(QUERY);
    const update = () => setReduced(mq.matches);
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return reduced;
}

/** Seconds since mount, ticking ~20 times a second while the tab is visible; frozen at 0 when disabled. */
export function useAnimationTime(enabled: boolean): number {
  const [time, setTime] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let frame = 0;
    let last = 0;
    const start = performance.now();
    const tick = (now: number) => {
      if (!document.hidden && now - last > 50) {
        last = now;
        setTime((now - start) / 1000);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [enabled]);
  return enabled ? time : 0;
}
