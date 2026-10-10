import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import type { Feature, FeedItem, ZoneProps } from "@/lib/api/types";
import { server } from "@/test/msw";
import { LiveFeed } from "./LiveFeed";
import { ZonePreview } from "./ZonePreview";

const item = (n: number, extra: Partial<FeedItem> = {}): FeedItem => ({
  id: `00000000-0000-0000-0000-00000000000${n}`, title: `Title ${n}`, english_summary: `Tankers late in ward ${n}`,
  quote: "no water", place: "Mahadevapura", source: "rss", domain: "thehindu.com", credibility: 0.8, severity: 4,
  hazards: ["drought"], published_at: new Date().toISOString(), url: "https://thehindu.com/x", zone_id: null, ...extra,
});

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

test("feed lists posts and loads the next page from the cursor", async () => {
  server.use(
    http.get("/api/v1/feed", ({ request }) => {
      const cursor = new URL(request.url).searchParams.get("cursor");
      return HttpResponse.json(cursor ? { items: [item(2)], next_cursor: null } : { items: [item(1)], next_cursor: "2026-10-10T00:00:00Z" });
    }),
  );
  wrap(<LiveFeed />);
  expect(await screen.findByText("Tankers late in ward 1")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Show older posts" }));
  expect(await screen.findByText("Tankers late in ward 2")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Show older posts" })).not.toBeInTheDocument();
});

test("feed shows untrusted text as text and an empty state when quiet", async () => {
  server.use(http.get("/api/v1/feed", () => HttpResponse.json({ items: [], next_cursor: null })));
  wrap(<LiveFeed />);
  expect(await screen.findByText("No posts yet")).toBeInTheDocument();
});

test("feed renders HTML in posts literally", async () => {
  server.use(http.get("/api/v1/feed", () =>
    HttpResponse.json({ items: [item(3, { english_summary: null, title: "<b>bold</b> claim" })], next_cursor: null })));
  const { container } = wrap(<LiveFeed />);
  expect(await screen.findByText("<b>bold</b> claim")).toBeInTheDocument();
  expect(container.querySelector("b")).toBeNull();
});

test("zone preview shows the essentials and links to the zone page", async () => {
  const zone: Feature<ZoneProps> = {
    type: "Feature", id: "abc", geometry: null,
    properties: { name: "Mohol, Solapur", hazard: "drought", zone_type: "rural", status: "active", score: 72.4,
      trend: "escalating", population_est: 120000, independent_sources: 3, centroid: [75.9, 17.7] },
  };
  const onClose = vi.fn();
  wrap(<ZonePreview zone={zone} onClose={onClose} />);
  expect(screen.getByRole("heading", { name: "Mohol, Solapur" })).toBeInTheDocument();
  expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "72.4");
  expect(screen.getByText("1.2 lakh")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open zone" })).toHaveAttribute("href", "/zones/abc");
  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalled();
});
