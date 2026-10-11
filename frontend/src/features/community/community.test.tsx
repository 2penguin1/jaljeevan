import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router";
import type { Campaign, Me, VolunteerTask } from "@/lib/api/types";
import { server } from "@/test/msw";
import { CommunityPage } from "./CommunityPage";

const CITIZEN: Me = { id: "c1", email: "asha@example.org", name: "Asha", role: "citizen", org_id: null, org_name: null };
const NGO: Me = { id: "n1", email: "ngo@relief.demo", name: "NGO lead", role: "ngo", org_id: "o1", org_name: "Jal Seva Foundation (demo)" };
const campaign: Campaign = { id: "k1", title: "Tankers for Akkalkot villages", story: "Wells have run dry.", goal_inr: 300000,
  pledged_inr: 75000, pledges: 6, zone_id: "z1", zone_name: "Akkalkot taluka, Solapur", ngo_name: "Jal Seva Foundation (demo)", created_at: "2026-10-11T10:00:00Z" };
const task: VolunteerTask = { id: "t1", title: "Hand out water cans", description: "Morning shifts", task_date: "2026-10-15", slots: 12,
  taken: 11, signed_up: false, zone_id: "z1", zone_name: "Akkalkot taluka, Solapur", ngo_name: "Jal Seva Foundation (demo)" };

function renderPage(me: Me | null) {
  server.use(
    http.get("/api/v1/auth/me", () => (me ? HttpResponse.json(me) : HttpResponse.json({ detail: "x" }, { status: 401 }))),
    http.get("/api/v1/campaigns", () => HttpResponse.json([campaign])),
    http.get("/api/v1/volunteer-tasks", () => HttpResponse.json([task])),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CommunityPage /></MemoryRouter></QueryClientProvider>);
}

test("everyone sees campaigns with progress and tasks with slots left", async () => {
  renderPage(null);
  const card = await screen.findByRole("article", { name: "Tankers for Akkalkot villages" });
  expect(within(card).getByText(/₹75,000 pledged of ₹3,00,000/)).toBeInTheDocument();
  expect(screen.getByRole("article", { name: "Hand out water cans" })).toHaveTextContent("1 of 12 places left");
  expect(screen.getAllByRole("link", { name: /Log in/ }).length).toBeGreaterThan(0);
});

test("a citizen pledges and signs up", async () => {
  const posts: unknown[] = [];
  server.use(
    http.post("/api/v1/campaigns/k1/pledges", async ({ request }) => { posts.push(await request.json()); return new HttpResponse(null, { status: 204 }); }),
    http.post("/api/v1/volunteer-tasks/t1/signups", () => { posts.push("signup"); return new HttpResponse(null, { status: 204 }); }),
  );
  renderPage(CITIZEN);
  const card = await screen.findByRole("article", { name: "Tankers for Akkalkot villages" });
  await userEvent.clear(within(card).getByLabelText("Pledge amount (₹)"));
  await userEvent.type(within(card).getByLabelText("Pledge amount (₹)"), "2500");
  await userEvent.click(within(card).getByRole("button", { name: "Pledge" }));
  await userEvent.click(within(screen.getByRole("article", { name: "Hand out water cans" })).getByRole("button", { name: "Sign up" }));
  expect(posts).toEqual([{ amount_inr: 2500, message: null }, "signup"]);
});

test("only NGO accounts see the forms to start campaigns and post tasks", async () => {
  renderPage(NGO);
  expect(await screen.findByRole("button", { name: "Start campaign" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Post task" })).toBeInTheDocument();
});
