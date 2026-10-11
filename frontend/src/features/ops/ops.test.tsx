import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router";
import type { OpsSummary } from "@/lib/api/types";
import { server } from "@/test/msw";
import { OpsPage } from "./OpsPage";

const ops = (runs: OpsSummary["runs"]): OpsSummary => ({
  runs,
  indicators: [{ source: "chirps-spi", period: "2026-10-05", areas: 6822 }],
  totals: { signals: 353, classified: 257, rejected_by_reason: { too_old: 62, no_keyword: 21 },
    tokens: { input_tokens: 120000, output_tokens: 30000 }, batches_by_provider: { "groq:openai/gpt-oss-120b": 12, "bedrock:apac.amazon.nova-lite-v1:0": 15 } },
});
const stats = { active_zones: 2, watch_zones: 24, posts_analysed_7d: 353, people_affected: 3980116, sources: 47 };

function renderOps(body: OpsSummary) {
  server.use(
    http.get("/api/v1/ops/summary", () => HttpResponse.json(body)),
    http.get("/api/v1/stats/overview", () => HttpResponse.json(stats)),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><OpsPage /></MemoryRouter></QueryClientProvider>);
}

test("ops shows totals, rejection reasons and provider usage", async () => {
  renderOps(ops([{ id: "r1", kind: "local", started_at: "2026-10-10T10:00:00Z", finished_at: "2026-10-10T10:03:20Z",
    stats: { ingest: { gdelt: { fetched: 40, inserted: 12 }, rss: { error: "rss: HTTP 500" } }, classify: { classified: 9 }, zones: { active: 2 } } }]));
  expect(await screen.findByText("353")).toBeInTheDocument();
  expect(screen.getByText("1.5 lakh")).toBeInTheDocument(); // tokens
  const reasons = screen.getByRole("region", { name: "Why posts were set aside" });
  expect(within(reasons).getByText("Older than 30 days")).toBeInTheDocument();
  expect(within(reasons).getByText("62")).toBeInTheDocument();
  expect(screen.getByText("Amazon Nova Lite")).toBeInTheDocument();
  expect(screen.getByText("3m 20s")).toBeInTheDocument();
  expect(screen.getByText("1 source failed")).toBeInTheDocument();
  const data = screen.getByRole("region", { name: "Drought data" });
  expect(within(data).getByText("Rainfall (CHIRPS SPI)")).toBeInTheDocument();
  expect(within(data).getByText("6,822")).toBeInTheDocument();
});

test("ops explains when nothing has run yet", async () => {
  renderOps(ops([]));
  expect(await screen.findByText("No pipeline runs yet")).toBeInTheDocument();
});
