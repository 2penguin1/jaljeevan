import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { useLiveEvents, type LiveEvent } from "./useLiveEvents";

class FakeEventSource {
  static last: FakeEventSource;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }
  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    (this.listeners[type] ??= []).push(fn);
  }
  close() {
    this.closed = true;
  }
  emit(type: string, data?: unknown) {
    const event = new MessageEvent(type, { data: data === undefined ? undefined : JSON.stringify(data) });
    this.listeners[type]?.forEach((fn) => fn(event));
  }
}

test("tracks connection status, parses events and invalidates the right queries", () => {
  vi.stubGlobal("EventSource", FakeEventSource);
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const received: LiveEvent[] = [];
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result, unmount } = renderHook(() => useLiveEvents((e) => received.push(e)), { wrapper });

  expect(result.current.status).toBe("connecting");
  expect(FakeEventSource.last.url).toBe("/api/v1/live");
  act(() => FakeEventSource.last.emit("open"));
  expect(result.current.status).toBe("live");
  act(() => FakeEventSource.last.emit("error"));
  expect(result.current.status).toBe("reconnecting");
  act(() => FakeEventSource.last.emit("open"));
  expect(result.current.status).toBe("live");

  act(() => FakeEventSource.last.emit("signal", { id: "s1" }));
  act(() => FakeEventSource.last.emit("zone", { zone_id: "z1", score: 80, hazard: "flood", name: "Patna" }));
  act(() => FakeEventSource.last.emit("signal", undefined)); // malformed: ignored, no crash
  expect(received).toEqual([
    { event: "signal", data: { id: "s1" } },
    { event: "zone", data: { zone_id: "z1", score: 80, hazard: "flood", name: "Patna" } },
  ]);
  const keys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
  expect(keys).toEqual(expect.arrayContaining(['["feed"]', '["map","signals"]', '["map","zones"]', '["zones"]', '["stats"]']));

  unmount();
  expect(FakeEventSource.last.closed).toBe(true);
  vi.unstubAllGlobals();
});

test("a stream the browser gave up on (CLOSED) is reopened with backoff", () => {
  vi.useFakeTimers();
  const created: FakeEventSource[] = [];
  class Tracking extends FakeEventSource {
    static CLOSED = 2;
    readyState = 1;
    constructor(url: string) {
      super(url);
      created.push(this);
    }
  }
  vi.stubGlobal("EventSource", Tracking);
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result, unmount } = renderHook(() => useLiveEvents(), { wrapper });
  act(() => {
    (created[0] as Tracking).readyState = 2; // e.g. the proxy answered 500 while the API restarted
    created[0].emit("error");
  });
  expect(result.current.status).toBe("reconnecting");
  act(() => vi.advanceTimersByTime(20_000));
  expect(created).toHaveLength(2);
  act(() => created[1].emit("open"));
  expect(result.current.status).toBe("live");
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["map", "zones"] }); // catch up on missed events
  unmount();
  expect(created[1].closed).toBe(true);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
