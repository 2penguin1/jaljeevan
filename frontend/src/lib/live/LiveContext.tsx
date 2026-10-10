import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useLiveEvents, type LiveEvent, type LiveStatus } from "./useLiveEvents";

type Listener = (e: LiveEvent) => void;
const LiveContext = createContext<{ status: LiveStatus; subscribe: (fn: Listener) => () => void } | null>(null);

/** One SSE connection for the whole app shell; pages subscribe to it instead of opening their own. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const listeners = useRef(new Set<Listener>());
  const { status } = useLiveEvents((e) => listeners.current.forEach((fn) => fn(e)));
  const [subscribe] = useState(() => (fn: Listener) => {
    listeners.current.add(fn);
    return () => void listeners.current.delete(fn);
  });
  return <LiveContext.Provider value={{ status, subscribe }}>{children}</LiveContext.Provider>;
}

export function useLiveStatus(): LiveStatus {
  return useContext(LiveContext)?.status ?? "connecting";
}

export function useLiveSubscription(fn: Listener) {
  const ctx = useContext(LiveContext);
  const handler = useRef(fn);
  handler.current = fn;
  useEffect(() => ctx?.subscribe((e) => handler.current(e)), [ctx]);
}
