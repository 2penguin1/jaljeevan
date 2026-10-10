import type { RouteObject } from "react-router";
import { AppShell } from "./AppShell";
import { RouteError } from "./RouteError";

// Every page is a lazy chunk: three.js only loads on "/", maplibre/deck.gl only on "/map".
export const routes: RouteObject[] = [
  {
    path: "/",
    errorElement: <RouteError />,
    lazy: () => import("@/features/landing/LandingPage").then((m) => ({ Component: m.LandingPage })),
  },
  {
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { path: "/map", handle: { title: "Live map" }, lazy: () => import("@/features/map/MapPage").then((m) => ({ Component: m.MapPage })) },
      { path: "/zones", handle: { title: "Zones" }, lazy: () => import("@/features/zones/ZonesPage").then((m) => ({ Component: m.ZonesPage })) },
      {
        path: "/zones/:zoneId",
        handle: { title: "Zone" },
        lazy: () => import("@/features/zones/ZonePage").then((m) => ({ Component: m.ZonePage })),
      },
      { path: "/ops", handle: { title: "Pipeline health" }, lazy: () => import("@/features/ops/OpsPage").then((m) => ({ Component: m.OpsPage })) },
      { path: "*", lazy: () => import("./NotFound").then((m) => ({ Component: m.NotFound })) },
    ],
  },
];
