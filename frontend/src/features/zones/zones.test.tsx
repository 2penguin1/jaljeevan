import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { ZoneDetail, ZoneSummary } from "@/lib/api/types";
import { server } from "@/test/msw";
import { roundShares } from "./ScoreBreakdown";
import { ZonePage } from "./ZonePage";
import { ZonesPage } from "./ZonesPage";
import { outlinePath } from "./ZoneMiniMap";

const ZID = "11111111-1111-1111-1111-111111111111";
const summary = (id: string, hazard: ZoneSummary["hazard"], score: number): ZoneSummary => ({
  id, name: `${hazard} zone ${score}`, hazard, zone_type: "rural", status: "active", score, trend: "stable",
  independent_sources: 2, population_est: 50000, population_urban: 12000, population_source: "worldpop",
  last_seen: new Date().toISOString(),
});

const detail: ZoneDetail = {
  zone: { ...summary(ZID, "drought", 72), name: "Mohol, Solapur", district: "Solapur", centroid: [75.9, 17.7],
    geometry: { type: "Polygon", coordinates: [[[75.8, 17.6], [76, 17.6], [76, 17.8], [75.8, 17.6]]] } },
  evidence: [
    { signal_id: "a", quote: "<img src=x onerror=alert(1)> taps dry for 9 days", summary: "Taps dry", title: "t",
      source: "rss", domain: "thehindu.com", credibility: 0.8, weight: 0.6, severity: 4, url: "https://thehindu.com/a",
      published_at: new Date().toISOString(), place: "Mohol" },
    { signal_id: "b", quote: "tankers late", summary: "Tankers late", title: "t2", source: "reddit", domain: "reddit.com",
      credibility: 0.4, weight: 0.3, severity: 3, url: null, published_at: null, place: null },
  ],
  score_breakdown: { contributions: [{ signal_id: "a", weight: 0.6, share: 2 / 3 }, { signal_id: "b", weight: 0.3, share: 1 / 3 }],
    indicator_boost: 0.4, independent_sources: 2, rule_met: true },
  trend: [{ at: "2026-10-09T00:00:00Z", score: 60 }, { at: "2026-10-10T00:00:00Z", score: 72 }],
  indicators: { label: "Rainfall vs normal (%)", value: -55, band: "severe" },
};

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [{ path: "/zones", element: <ZonesPage /> }, { path: "/zones/:zoneId", element: <ZonePage /> }],
    { initialEntries: [path] },
  );
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("zones list filters by hazard through the URL", async () => {
  server.use(http.get("/api/v1/zones", ({ request }) => {
    const hazard = new URL(request.url).searchParams.get("hazard");
    const all = [summary("1", "drought", 80), summary("2", "flood", 65)];
    return HttpResponse.json(hazard ? all.filter((z) => z.hazard === hazard) : all);
  }));
  const router = renderAt("/zones");
  expect(await screen.findByText("flood zone 65")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "flood zone 65" })).toHaveAttribute("href", "/zones/2"); // keyboard path
  await userEvent.click(screen.getByRole("button", { name: /Drought/ }));
  expect(router.state.location.search).toBe("?hazard=drought");
  expect(await screen.findByText("drought zone 80")).toBeInTheDocument();
  expect(screen.queryByText("flood zone 65")).not.toBeInTheDocument();
});

test("zones list explains an empty result", async () => {
  server.use(http.get("/api/v1/zones", () => HttpResponse.json([])));
  renderAt("/zones?hazard=heat");
  expect(await screen.findByText("No heat zones right now")).toBeInTheDocument();
});

test("zone page shows evidence as text and the score arithmetic", async () => {
  server.use(http.get(`/api/v1/zones/${ZID}`, () => HttpResponse.json(detail)));
  renderAt(`/zones/${ZID}`);
  expect(await screen.findByRole("heading", { level: 1, name: "Mohol, Solapur" })).toBeInTheDocument();
  expect(screen.getByText(/taps dry for 9 days/)).toBeInTheDocument();
  expect(document.querySelector("main img, img[src='x']")).toBeNull();
  const breakdown = screen.getByRole("region", { name: "How the score adds up" });
  expect(within(breakdown).getByText("67%")).toBeInTheDocument();
  expect(within(breakdown).getByText("33%")).toBeInTheDocument();
  expect(within(breakdown).getByText(/2 independent sources/)).toBeInTheDocument();
  expect(screen.getByText("People living in the zone area")).toBeInTheDocument();
  expect(screen.getByText("12,000 urban, 38,000 rural")).toBeInTheDocument();
});

test("unknown or malformed zone ids say so and link back", async () => {
  server.use(http.get("/api/v1/zones/abc", () =>
    HttpResponse.json({ detail: [{ msg: "Input should be a valid UUID" }] }, { status: 422 })));
  renderAt("/zones/abc");
  expect(await screen.findByText("Zone not found")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to all zones" })).toHaveAttribute("href", "/zones");
});

test("shares are rounded so they always add up to 100", () => {
  expect(roundShares([1 / 3, 1 / 3, 1 / 3])).toEqual([34, 33, 33]);
  expect(roundShares([2 / 3, 1 / 3]).reduce((a, b) => a + b, 0)).toBe(100);
  expect(roundShares([])).toEqual([]);
});

test("mini map draws polygons and multipolygons inside its box", () => {
  const path = outlinePath({ type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 0]]] }, 100, 100);
  expect(path.startsWith("M")).toBe(true);
  expect(outlinePath(null, 100, 100)).toBe("");
  const multi = outlinePath({ type: "MultiPolygon", coordinates: [[[[0, 0], [1, 0], [1, 1], [0, 0]]], [[[5, 5], [6, 5], [6, 6], [5, 5]]]] }, 100, 100);
  expect(multi.match(/M/g)).toHaveLength(2);
});

test("a drought zone shows the measured data behind it, labelled as indicative", async () => {
  const drought: ZoneDetail = {
    ...detail,
    zone: { ...detail.zone, zone_type: "taluka", name: "Mohol taluka, Solapur" },
    indicators: null,
    drought: {
      label: "Indicative drought footprint (GoI Drought Manual, rainfall trigger + soil moisture anomaly)",
      rules_version: "v1", level: "severe", trigger1: true, t1_class: "severe", soil_class: "severe",
      spi_6p: -1.3, spi_18p: -2.7, spi_period: "2026-10-05", soil_anomaly: -1.6, soil_period: "2026-09-30",
      people_in_dry_areas: 210000, people_in_dry_areas_urban: 30000, imd_district_departure_pct: -45,
      imd_deficient: true, reasons: ["Rainfall over the last 3 months is severely below normal (SPI -2.7)"],
      declared: { severity: "severe", declared_on: "2026-09-25", order_ref: "GR 25 Sep 2026",
        source_url: "javascript:alert(1)" },
    },
  };
  server.use(http.get(`/api/v1/zones/${ZID}`, () => HttpResponse.json(drought)));
  renderAt(`/zones/${ZID}`);
  const panel = await screen.findByRole("region", { name: "Measured drought data" });
  expect(within(panel).getByText(/Indicative drought footprint/)).toBeInTheDocument();
  expect(within(panel).getByText("−2.7")).toBeInTheDocument();
  expect(within(panel).getByText("Extremely dry")).toBeInTheDocument();
  expect(within(panel).getByText("2.1 lakh")).toBeInTheDocument();
  expect(within(panel).getByText(/Declared severe drought/)).toBeInTheDocument();
  expect(panel.querySelector('a[href^="javascript"]')).toBeNull();
  expect(screen.getByText("Taluka")).toBeInTheDocument();
});
