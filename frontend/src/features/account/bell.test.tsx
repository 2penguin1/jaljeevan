import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router";
import { server } from "@/test/msw";
import { NotificationBell } from "./NotificationBell";

test("the bell shows unread notifications, links to the tender and marks them read", async () => {
  let marked: unknown = null;
  server.use(
    http.get("/api/v1/notifications", () => HttpResponse.json({ unread: 2, items: [
      { id: "n1", kind: "tender_invite", text: "New tender: 90 kL a day near Akkalkot", link: "/tenders/t1", created_at: "2026-10-11T16:00:00Z", read: false },
      { id: "n2", kind: "bid_update", text: "Akkalkot: Government accepted", link: "/tenders/t1", created_at: "2026-10-11T16:05:00Z", read: false },
    ] })),
    http.post("/api/v1/notifications/read", async ({ request }) => { marked = await request.json(); return new HttpResponse(null, { status: 204 }); }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><NotificationBell /></MemoryRouter></QueryClientProvider>);
  const bell = await screen.findByRole("button", { name: "Notifications, 2 unread" });
  await userEvent.click(bell);
  expect(screen.getByRole("link", { name: /New tender: 90 kL a day near Akkalkot/ })).toHaveAttribute("href", "/tenders/t1");
  await userEvent.click(screen.getByRole("button", { name: "Mark all read" }));
  expect(marked).toEqual({});
});
