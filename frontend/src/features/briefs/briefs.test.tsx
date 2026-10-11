import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { Brief, Me } from "@/lib/api/types";
import { server } from "@/test/msw";
import { BriefCard } from "./BriefCard";

const ZID = "11111111-1111-1111-1111-111111111111";
const OFFICER: Me = { id: "u0", email: "officer@relief.demo", name: "Officer", role: "gov_admin", org_id: "g", org_name: "Relief" };
const draft: Brief = {
  id: "b1", zone_id: ZID, zone_name: "Akkalkot taluka, Solapur", version: 1, status: "draft",
  summary: "Wells are drying up and farmers are seeking relief.",
  actions: [{ key: "tanker_rounds", text: "Start daily drinking-water tanker rounds to the worst-hit villages" }],
  cited_signal_ids: ["s1"], people: 29999, need_per_day: 600, units_per_day: 60, duration_days: 30, budget_inr: 1080000,
  suggested_price_per_unit: 60, formula: "2,99,990 rural people x 10% on tankers x 20 L a day = 600 kL a day",
  written_by: "groq:openai/gpt-oss-120b", review_notes: null, created_at: "2026-10-11T16:00:00Z",
};

function renderCard(me: Me | null, brief: Brief | null) {
  server.use(
    http.get("/api/v1/auth/me", () => (me ? HttpResponse.json(me) : HttpResponse.json({ detail: "x" }, { status: 401 }))),
    http.get(`/api/v1/zones/${ZID}/brief`, () => HttpResponse.json(brief)),
  );
  const router = createMemoryRouter([{ path: "/z", element: <BriefCard zoneId={ZID} /> }, { path: "/tenders/:id", element: <p>tender page</p> }],
    { initialEntries: ["/z"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

test("an officer sees the draft: AI words, code numbers, and approving publishes the tender", async () => {
  let approved = false;
  server.use(http.post("/api/v1/briefs/b1/approve", () => { approved = true; return HttpResponse.json({ tender_id: "t9" }); }));
  renderCard(OFFICER, draft);
  expect(await screen.findByText("Wells are drying up and farmers are seeking relief.")).toBeInTheDocument();
  expect(screen.getByText("₹10,80,000")).toBeInTheDocument();
  expect(screen.getByText(/Words by AI \(groq/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Approve and publish tender" }));
  expect(await screen.findByText("tender page")).toBeInTheDocument();
  expect(approved).toBe(true);
});

test("an officer can draft a brief when there is none", async () => {
  let drafted = false;
  server.use(http.post(`/api/v1/zones/${ZID}/briefs`, () => { drafted = true; return HttpResponse.json(draft, { status: 201 }); }));
  renderCard(OFFICER, null);
  await userEvent.click(await screen.findByRole("button", { name: "Draft a relief brief" }));
  expect(drafted).toBe(true);
});

test("visitors see nothing until a brief is approved", async () => {
  renderCard(null, null);
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByRole("region", { name: "Relief brief" })).not.toBeInTheDocument();
});
