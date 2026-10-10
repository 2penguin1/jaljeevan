import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { Hazard } from "@/lib/api/types";

export type LiveEvent =
  | { event: "signal"; data: { id: string } }
  | { event: "zone"; data: { zone_id: string; score: number; hazard: Hazard; name: string } };

export type LiveStatus = "connecting" | "live" | "reconnecting";

const INVALIDATES: Record<LiveEvent["event"], string[][]> = {
  signal: [["feed"], ["map", "signals"]],
  zone: [["map", "zones"], ["zones"], ["stats"]],
};

/** One EventSource per mounted consumer, kept open across drops and API restarts. */
export function useLiveEvents(onEvent?: (e: LiveEvent) => void): { status: LiveStatus } {
  const client = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    let source: EventSource | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let dropped = false;
    const connect = () => {
      source = new EventSource("/api/v1/live");
      source.addEventListener("open", () => {
        attempt = 0;
        setStatus("live");
        if (dropped) {
          dropped = false; // events sent while we were away are lost: refetch everything live-driven
          for (const queryKey of Object.values(INVALIDATES).flat()) client.invalidateQueries({ queryKey });
        }
      });
      source.addEventListener("error", () => {
        dropped = true;
        setStatus("reconnecting");
        // The browser retries dropped connections itself, but gives up (CLOSED) after a non-200 answer,
        // e.g. a proxy 500/502 while the API restarts. Reopen it ourselves, backing off up to 15 s.
        if (source?.readyState === EventSource.CLOSED) {
          source.close();
          timer = setTimeout(connect, Math.min(15_000, 1_000 * 2 ** attempt++));
        }
      });
      for (const name of Object.keys(INVALIDATES) as LiveEvent["event"][]) {
        source.addEventListener(name, (e) => {
          let data: unknown;
          try {
            data = JSON.parse((e as MessageEvent).data);
          } catch {
            return; // malformed event: ignore it rather than break the stream
          }
          if (!data || typeof data !== "object") return;
          for (const queryKey of INVALIDATES[name]) client.invalidateQueries({ queryKey });
          handler.current?.({ event: name, data } as LiveEvent);
        });
      }
    };
    connect();
    return () => {
      clearTimeout(timer);
      source?.close();
    };
  }, [client]);

  return { status };
}
