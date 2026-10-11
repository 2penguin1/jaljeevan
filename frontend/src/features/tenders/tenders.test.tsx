import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import { InboxPage } from "@/features/account/InboxPage";
import { LoginPage } from "@/features/account/LoginPage";
import type { Me, ReliefNeed, TenderDetail } from "@/lib/api/types";
import { server } from "@/test/msw";
import { ReliefNeedCard } from "./ReliefNeedCard";
import { TenderPage } from "./TenderPage";

const TID = "22222222-2222-2222-2222-222222222222";
const ZID = "11111111-1111-1111-1111-111111111111";
const bid = (id: string, name: string, status: string, turn: string, qty: number) => ({
  id, vendor_id: `v-${id}`, vendor_name: name, distance_km: 12, rank_score: 0.8, version: 1,
  reason: "12 km by road, ₹55/kL, 12 tankers (120 kL a day), 90% of past orders delivered", status, turn,
  offer: { version: 1, price_per_unit: 60, qty_per_day: qty, proposed_by_side: "gov", status: status === "accepted" ? "agreed" : "proposed", note: null },
  messages: [{ side: "system", body: "Invited: 12 km by road", at: "2026-10-11T15:00:00Z", author: null }],
});
const tender: TenderDetail = {
  id: TID, zone_id: ZID, zone_name: "Akkalkot taluka, Solapur", status: "published", qty_per_day: 600, duration_days: 30,
  price_per_unit: 60, radius_km: 100, published_at: "2026-10-11T15:00:00Z", committed_kl_per_day: 100, waiting_for_gov: 0,
  bids: [bid("b1", "Near Cheap Tankers (demo)", "accepted", "none", 100), bid("b2", "Latur Neer Logistics (demo)", "invited", "vendor", 120)],
};
const VENDOR: Me = { id: "u1", email: "latur@vendor.demo", name: "Latur desk", role: "vendor", org_id: "v-b2", org_name: "Latur Neer Logistics (demo)" };
const OFFICER: Me = { id: "u0", email: "officer@relief.demo", name: "Demo relief officer", role: "gov_admin", org_id: "g", org_name: "Relief" };

function session(me: Me | null) {
  server.use(http.get("/api/v1/auth/me", () => (me ? HttpResponse.json(me) : HttpResponse.json({ detail: "Please log in" }, { status: 401 }))));
}

function renderAt(element: React.ReactNode, path: string, route: string) {
  const router = createMemoryRouter(
    [{ path: route, element }, { path: "/tenders/:tenderId", element: <p>tender page</p> }, { path: "/inbox", element: <p>inbox page</p> }],
    { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

test("anyone can follow a tender: who was invited, why, and how much water is committed", async () => {
  session(null);
  server.use(http.get(`/api/v1/tenders/${TID}`, () => HttpResponse.json(tender)));
  renderAt(<TenderPage />, `/tenders/${TID}`, "/tenders/:tenderId");
  expect(await screen.findByRole("heading", { name: /Akkalkot taluka, Solapur/ })).toBeInTheDocument();
  expect(screen.getByText(/100 of 600 kL a day committed/)).toBeInTheDocument();
  expect(screen.getByRole("article", { name: "Near Cheap Tankers (demo)" })).toHaveTextContent("Agreed");
  expect(screen.queryByRole("button", { name: "Accept offer" })).not.toBeInTheDocument();
  expect(await screen.findByText(/to take part/)).toBeInTheDocument();
});

test("a vendor sees only its own bid and answers with the version it saw", async () => {
  session(VENDOR);
  let sent: unknown = null;
  server.use(
    http.get(`/api/v1/tenders/${TID}`, () => HttpResponse.json(tender)),
    http.post(`/api/v1/tenders/${TID}/bids/b2/actions`, async ({ request }) => { sent = await request.json(); return HttpResponse.json(tender); }),
  );
  renderAt(<TenderPage />, `/tenders/${TID}`, "/tenders/:tenderId");
  const card = await screen.findByRole("article", { name: "Latur Neer Logistics (demo)" });
  expect(screen.queryByRole("article", { name: "Near Cheap Tankers (demo)" })).not.toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Accept offer" }));
  expect(sent).toEqual({ action: "accept", expected_version: 1 });
});

test("the officer can raise the price and write in a bid thread", async () => {
  session(OFFICER);
  const posts: unknown[] = [];
  server.use(
    http.get(`/api/v1/tenders/${TID}`, () => HttpResponse.json(tender)),
    http.post(`/api/v1/tenders/${TID}/raise-price`, async ({ request }) => { posts.push(await request.json()); return HttpResponse.json(tender); }),
    http.post(`/api/v1/tenders/${TID}/bids/b2/actions`, async ({ request }) => { posts.push(await request.json()); return HttpResponse.json(tender); }),
  );
  renderAt(<TenderPage />, `/tenders/${TID}`, "/tenders/:tenderId");
  await userEvent.click(await screen.findByRole("button", { name: "Raise price" }));
  const card = screen.getByRole("article", { name: "Latur Neer Logistics (demo)" });
  await userEvent.type(within(card).getByLabelText("Message to the other side"), "Can you start Monday?");
  await userEvent.click(within(card).getByRole("button", { name: "Send" }));
  expect(posts).toEqual([{ price_per_unit: 65 }, { action: "message", body: "Can you start Monday?" }]);
});

const NEED: ReliefNeed = { people: 29999, kl_per_day: 600, tanker_trips_per_day: 60, share: 0.1, suggested_price: 62,
  formula: "2,99,990 rural people x 10% on tankers x 20 L a day = 600 kL a day = 60 trips of a 10 kL tanker" };

test("the relief need card shows the arithmetic to everyone but only an officer can publish", async () => {
  session(null);
  server.use(http.get(`/api/v1/zones/${ZID}/relief-need`, () => HttpResponse.json(NEED)));
  renderAt(<ReliefNeedCard zoneId={ZID} />, "/z", "/z");
  expect(await screen.findByText(/x 20 L a day = 600 kL a day/)).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Log in as a relief officer" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Create tanker tender" })).not.toBeInTheDocument();
});

test("an officer publishes a prefilled tender from the relief need", async () => {
  session(OFFICER);
  let created: unknown = null;
  server.use(
    http.get(`/api/v1/zones/${ZID}/relief-need`, () => HttpResponse.json(NEED)),
    http.post("/api/v1/tenders", async ({ request }) => { created = await request.json(); return HttpResponse.json({ id: TID }, { status: 201 }); }),
  );
  renderAt(<ReliefNeedCard zoneId={ZID} />, "/z", "/z");
  await userEvent.click(await screen.findByRole("button", { name: "Create tanker tender" }));
  await userEvent.click(screen.getByRole("button", { name: "Publish tender" }));
  expect(await screen.findByText("tender page")).toBeInTheDocument();
  expect(created).toEqual({ zone_id: ZID, qty_per_day: 600, duration_days: 30, price_per_unit: 62, radius_km: 100 });
});

test("logging in as a vendor opens the inbox", async () => {
  let sent: unknown = null;
  server.use(http.post("/api/v1/auth/login", async ({ request }) => { sent = await request.json(); return HttpResponse.json(VENDOR); }));
  renderAt(<LoginPage />, "/login", "/login");
  await userEvent.type(screen.getByLabelText("Email"), "latur@vendor.demo");
  await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
  expect(await screen.findByText("inbox page")).toBeInTheDocument();
  expect(sent).toEqual({ email: "latur@vendor.demo", password: "secret-pass" });
});

test("the vendor inbox sorts bids by whose move it is", async () => {
  session(VENDOR);
  const item = { ...bid("b2", "Latur Neer Logistics (demo)", "invited", "vendor", 120), tender_id: TID, zone_name: "Akkalkot taluka, Solapur", duration_days: 30 };
  server.use(http.get("/api/v1/inbox", () => HttpResponse.json({ needs_action: [item], waiting: [], closed: [] })));
  renderAt(<InboxPage />, "/inbox", "/inbox");
  const needs = await screen.findByRole("region", { name: "Needs your answer" });
  expect(within(needs).getByText("Akkalkot taluka, Solapur")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Waiting for the government" })).toHaveTextContent("No open offers");
});
