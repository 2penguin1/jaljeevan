import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { ReliefNeed, TenderDetail } from "@/lib/api/types";
import { server } from "@/test/msw";
import { ReliefNeedCard } from "./ReliefNeedCard";
import { TenderPage } from "./TenderPage";

const TID = "22222222-2222-2222-2222-222222222222";
const ZID = "11111111-1111-1111-1111-111111111111";
const bid = (id: string, name: string, status: string, turn: string, qty: number) => ({
  id, vendor_id: `v-${id}`, vendor_name: name, distance_km: 12, rank_score: 0.8,
  reason: "12 km by road, ₹55/kL, 12 tankers (120 kL a day), 90% of past orders delivered", status, turn,
  offer: { version: 1, price_per_unit: 60, qty_per_day: qty, proposed_by_side: "gov", status: status === "accepted" ? "agreed" : "proposed", note: null },
  messages: [{ side: "system", body: "Invited: 12 km by road", at: "2026-10-11T15:00:00Z" }],
});
const tender: TenderDetail = {
  id: TID, zone_id: ZID, zone_name: "Akkalkot taluka, Solapur", status: "published", qty_per_day: 600, duration_days: 30,
  price_per_unit: 60, radius_km: 100, published_at: "2026-10-11T15:00:00Z", committed_kl_per_day: 100,
  bids: [bid("b1", "Near Cheap Tankers (demo)", "accepted", "none", 100), bid("b2", "Latur Neer Logistics (demo)", "invited", "vendor", 120)],
};

function renderAt(element: React.ReactNode, path: string, route: string) {
  const router = createMemoryRouter([{ path: route, element }, { path: "/tenders/:tenderId", element: <p>tender page</p> }],
    { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

test("a tender shows who was invited, why, and how much water is committed", async () => {
  server.use(http.get(`/api/v1/tenders/${TID}`, () => HttpResponse.json(tender)));
  renderAt(<TenderPage />, `/tenders/${TID}`, "/tenders/:tenderId");
  expect(await screen.findByRole("heading", { name: /Akkalkot taluka, Solapur/ })).toBeInTheDocument();
  expect(screen.getByText(/100 of 600 kL a day committed/)).toBeInTheDocument();
  expect(screen.getAllByText(/12 km by road/).length).toBeGreaterThan(0);
  expect(screen.getByRole("article", { name: "Near Cheap Tankers (demo)" })).toHaveTextContent("Agreed");
});

test("viewing as a vendor whose turn it is shows the answer buttons and sends the vendor's answer", async () => {
  let sent: unknown = null;
  server.use(
    http.get(`/api/v1/tenders/${TID}`, () => HttpResponse.json(tender)),
    http.post(`/api/v1/tenders/${TID}/bids/b2/actions`, async ({ request }) => {
      sent = { body: await request.json(), code: request.headers.get("X-Admin-Token") };
      return HttpResponse.json(tender);
    }),
  );
  sessionStorage.setItem("demo-access-code", "code-123");
  renderAt(<TenderPage />, `/tenders/${TID}`, "/tenders/:tenderId");
  await userEvent.selectOptions(await screen.findByLabelText("Viewing as"), "v-b2");
  const card = screen.getByRole("article", { name: "Latur Neer Logistics (demo)" });
  await userEvent.click(within(card).getByRole("button", { name: "Accept offer" }));
  expect(sent).toEqual({ body: { side: "vendor", action: "accept" }, code: "code-123" });
});

test("the relief need card shows the arithmetic and prefills a tender", async () => {
  const need: ReliefNeed = { people: 29999, kl_per_day: 600, tanker_trips_per_day: 60, share: 0.1, suggested_price: 62,
    formula: "2,99,990 rural people x 10% on tankers x 20 L a day = 600 kL a day = 60 trips of a 10 kL tanker" };
  let created: unknown = null;
  server.use(
    http.get(`/api/v1/zones/${ZID}/relief-need`, () => HttpResponse.json(need)),
    http.post("/api/v1/tenders", async ({ request }) => { created = await request.json(); return HttpResponse.json({ id: TID }, { status: 201 }); }),
  );
  sessionStorage.setItem("demo-access-code", "code-123");
  renderAt(<ReliefNeedCard zoneId={ZID} />, "/z", "/z");
  expect(await screen.findByText(/x 20 L a day = 600 kL a day/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Create tanker tender" }));
  await userEvent.click(screen.getByRole("button", { name: "Publish tender" }));
  expect(await screen.findByText("tender page")).toBeInTheDocument();
  expect(created).toEqual({ zone_id: ZID, qty_per_day: 600, duration_days: 30, price_per_unit: 62, radius_km: 100 });
});
