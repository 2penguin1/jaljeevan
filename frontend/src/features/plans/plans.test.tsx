import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { Me, Plan } from "@/lib/api/types";
import { server } from "@/test/msw";
import { PlanCard } from "./PlanCard";
import { PlanPrintPage } from "./PlanPrintPage";

const ZID = "11111111-1111-1111-1111-111111111111";
const OFFICER: Me = { id: "u0", email: "officer@relief.demo", name: "Officer", role: "gov_admin", org_id: "g", org_name: "Relief" };
const plan: Plan = {
  id: "p1", zone_id: ZID, zone_name: "Akkalkot taluka, Solapur", hazard: "drought", version: 1, status: "approved",
  title: "Long-term water plan for Akkalkot taluka, Solapur", problem_summary: "Groundwater keeps falling.",
  options: [{ key: "farm_ponds", label: "Farm ponds to store monsoon run-off", unit: "pond", quantity: 1000, unit_cost_inr: 150000,
    cost_inr: 150000000, basis: "200 villages x 5 pond per village x ₹150,000 each (indicative)" }],
  total_cost_inr: 150000000, written_by: "groq:openai/gpt-oss-120b",
  trend: { first_score: 40, last_score: 79, since: "2026-09-01", points: 12 }, review_notes: null, created_at: "2026-10-11T16:00:00Z",
};

function renderAt(element: React.ReactNode, path: string, route: string, me: Me | null, routes: Record<string, Plan | null>) {
  server.use(
    http.get("/api/v1/auth/me", () => (me ? HttpResponse.json(me) : HttpResponse.json({ detail: "x" }, { status: 401 }))),
    ...Object.entries(routes).map(([url, body]) => http.get(url, () => HttpResponse.json(body))),
  );
  const router = createMemoryRouter([{ path: route, element }], { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

test("an approved plan shows menu options with code costs and a printable one-pager", async () => {
  renderAt(<PlanCard zoneId={ZID} />, "/z", "/z", null, { [`/api/v1/zones/${ZID}/plan`]: plan });
  expect(await screen.findByText("Farm ponds to store monsoon run-off")).toBeInTheDocument();
  expect(screen.getByRole("row", { name: /Total \(indicative\)/ })).toHaveTextContent("₹15,00,00,000");
  expect(screen.getByRole("link", { name: "Print one-pager" })).toHaveAttribute("href", "/plans/p1/print");
});

test("an officer drafts a plan when there is none", async () => {
  let drafted = false;
  server.use(http.post(`/api/v1/zones/${ZID}/plans`, () => { drafted = true; return HttpResponse.json({ ...plan, status: "draft" }, { status: 201 }); }));
  renderAt(<PlanCard zoneId={ZID} />, "/z", "/z", OFFICER, { [`/api/v1/zones/${ZID}/plan`]: null });
  await userEvent.click(await screen.findByRole("button", { name: "Draft a long-term plan" }));
  expect(drafted).toBe(true);
});

test("the print page lays out the plan for paper", async () => {
  renderAt(<PlanPrintPage />, "/plans/p1/print", "/plans/:planId/print", null, { "/api/v1/plans/p1": plan });
  expect(await screen.findByRole("heading", { name: "Long-term water plan for Akkalkot taluka, Solapur" })).toBeInTheDocument();
  expect(screen.getByText(/unit costs are indicative assumptions/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Print" })).toBeInTheDocument();
});
