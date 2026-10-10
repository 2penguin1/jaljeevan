import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router";
import { server } from "@/test/msw";
import { LandingPage } from "./LandingPage";

const sceneProps: Record<string, unknown>[] = [];
vi.mock("./Scene", () => ({
  default: (props: Record<string, unknown>) => {
    sceneProps.push(props);
    return <div data-testid="scene" />;
  },
}));

const stats = { active_zones: 2, watch_zones: 24, posts_analysed_7d: 353, people_affected: 3980116, sources: 47 };
const empty = { type: "FeatureCollection", features: [] };

function renderLanding() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><LandingPage /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  sceneProps.length = 0;
  server.use(http.get("/api/v1/map/zones", () => HttpResponse.json(empty)));
  // jsdom has no WebGL; pretend it does so the scene mounts
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as never);
});
afterEach(() => vi.restoreAllMocks());

test("one headline, one button to the map, three live numbers", async () => {
  server.use(http.get("/api/v1/stats/overview", () => HttpResponse.json(stats)));
  renderLanding();
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href") === "/map");
  expect(links).toHaveLength(1);
  expect(links[0]).toHaveTextContent("Open the live map");
  expect(await screen.findByText("39.8 lakh")).toBeInTheDocument();
  expect(screen.getByText("353")).toBeInTheDocument();
  expect(screen.getAllByRole("term")).toHaveLength(3);
  expect(screen.getByText("zones confirmed right now")).toBeInTheDocument();
});

test("numbers show a dash when the API is down, and the page still works", async () => {
  server.use(http.get("/api/v1/stats/overview", () => HttpResponse.json({ detail: "down" }, { status: 500 })));
  renderLanding();
  await vi.waitFor(() => expect(screen.getAllByText("—")).toHaveLength(3));
  expect(screen.getByRole("link", { name: "Open the live map" })).toBeInTheDocument();
});

test("reduced motion keeps the camera still", async () => {
  const original = window.matchMedia;
  window.matchMedia = ((q: string) => ({ ...original(q), matches: q.includes("reduce") })) as typeof window.matchMedia;
  server.use(http.get("/api/v1/stats/overview", () => HttpResponse.json(stats)));
  renderLanding();
  await screen.findByTestId("scene");
  expect(sceneProps.at(-1)?.motion).toBe(false);
  window.matchMedia = original;
});
