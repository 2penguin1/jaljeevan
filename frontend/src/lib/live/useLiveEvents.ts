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

/** One EventSource per mounted consumer. The browser reconnects by itself; we only mirror its state. */
export function useLiveEvents(onEvent?: (e: LiveEvent) => void): { status: LiveStatus } {
  const client = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource("/api/v1/live");
    source.addEventListener("open", () => setStatus("live"));
    source.addEventListener("error", () => setStatus("reconnecting"));
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
    return () => source.close();
  }, [client]);

  return { status };
}
