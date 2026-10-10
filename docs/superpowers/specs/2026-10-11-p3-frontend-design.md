# P3: frontend foundation, 3D landing page and live map (design)

**Status:** approved in brainstorming on 2026-10-11. This builds on `2026-10-10-mvp-design.md` (product) and `2026-10-11-backend-lld.md` (backend rules).

## Goal and audience
- **The public front door:** anyone (citizens, NGOs, judges) can see the live crisis map **without logging in**. Government and vendor actions arrive in P4, behind logins.
- **The visual centrepiece of the demo video.** The interface must be **premium and elegant, never generic "AI-looking"**.
- **Scope:** P3 builds the **design system and app shell that every later page reuses** (the P4 CRM screens and P5 community pages), plus:
  - a 3D landing page;
  - the live map;
  - a zones list;
  - a zone page;
  - an ops page;
  - the backend read APIs they need.

**Out of scope for P3:** logins/roles, briefs, tenders, community and plans (P4/P5), and AWS hosting (P2).

## 1. Backend read APIs
All endpoints are public and read-only. Each is a controller → query service → repository, following the LLD. They live under `/api/v1`; existing admin routes are unchanged.

| Endpoint | Response |
|---|---|
| `GET /map/zones?hazard={drought\|flood\|heat}` | GeoJSON FeatureCollection. Properties: `id, name, hazard, zone_type, status, score, trend, population_est, independent_sources, centroid` |
| `GET /map/districts?hazard=` | GeoJSON districts with `indicator_value`, `indicator_label` and `band` (none/moderate/severe), from the hazard's indicator source |
| `GET /map/signals?hazard=&hours=48` | Point features: `id, severity, source, title, published_at, zone_id`. Capped at 1,000, newest first |
| `GET /feed?cursor=&limit=50` | Relevant classified signals, newest first: `id, english_summary, quote, place, source, domain, credibility, severity, hazards, published_at, url, zone_id`; keyset cursor |
| `GET /zones?hazard=&status=` | Zone table rows |
| `GET /zones/{id}` | The zone plus `evidence[]` (quote(s), summary, source, credibility, weight, url, published_at), `score_breakdown` (per-signal weights, indicator boost, independent sources, rule satisfied), `trend[]` (snapshots) and `indicators` |
| `GET /stats/overview` | `active_zones, posts_analysed_7d, people_affected, sources` |
| `GET /ops/summary` | Last 20 runs with stats: per-source counts, rejection reasons, tokens per LLM provider |
| `GET /live` | Server-Sent Events (FastAPI `EventSourceResponse`). Events `signal` and `zone`, relayed from the Postgres channels `signal_classified` / `zone_escalated` |

**Rules:**
- District geometry is served simplified (`ST_SimplifyPreserveTopology`), with coordinates rounded to 4 decimals. It's cached in-process (cachetools TTL) and keyed by the latest indicator period.
- Unknown id → 404 and bad enum → 422, through the existing error handlers.
- The browser reconnects SSE automatically, and the server sends a heartbeat every 15 s.
- **No CORS:** in development, Vite proxies `/api`; in production, CloudFront serves both from one origin (P2).

## 2. Frontend architecture
- **One Vite + React + TypeScript app** in `frontend/`, with route-level code-splitting.
- **Data flows one way:** page → feature components → data hooks → API client. Components never call `fetch` themselves.

**Folders:**
```
src/app/         router, providers, layouts (MarketingLayout, AppShell)
src/design/      tokens.css (CSS variables → Tailwind v4 @theme)
src/components/ui/        shadcn primitives restyled to the tokens
src/components/patterns/  StatTile, HazardBadge, EvidenceQuote, ScoreMeter, Sparkline, DataTable, EmptyState, Skeletons
src/features/landing|map|zones|ops/
src/lib/api/     client + TypeScript types generated from the backend OpenAPI (openapi-typescript)
src/lib/hooks/   TanStack Query hooks;  src/lib/live/ useLiveEvents (SSE)
```

**State:**
- server data lives in TanStack Query;
- UI choices go in the URL (`/map?hazard=drought`);
- no global store.

**Libraries:**
- React Router 7, TanStack Query, Tailwind v4 + shadcn;
- `three` + `@react-three/fiber` + `@react-three/drei` (+ postprocessing bloom) for the landing page only;
- `maplibre-gl` v5 (globe projection) + deck.gl for map routes only;
- `motion`, Recharts, Lucide.

**Every data view has** a designed skeleton, an empty state and an inline error with retry. The live stream shows a "reconnecting" indicator when the connection drops.

## 3. Design system: "editorial + control room"
- **Colour:** dark-first, warm near-black.

| Role | Value |
|---|---|
| Canvas | `#0B0A09` |
| Surface | `#131210` |
| Raised | `#1B1916` |
| Hairline | warm white at 8% |
| Text | `#EDE8E1` / `#A39E96` / `#6E6A64` |
| **Drought** | amber `#E8A33D` |
| **Flood** | cyan `#3FB6D8` |
| **Heat** | red-orange `#F0533A` (also danger) |
| Success | sage `#7FB592` |

  Hazard colours always carry meaning, never decoration. **Watch** zones use the hazard colour at low opacity with a dashed outline; **active** zones are solid and "breathe".
- **Type:** Instrument Serif (display: landing, zone names, hero numbers), Geist (UI; 14 px base in the app, 16 px+ on the landing page), Geist Mono with tabular digits for every number.
- **Shape:** a 4 px grid, 6 px corners, 1 px hairlines. Depth comes from layered surfaces, not heavy shadows. Frosted glass appears only over 3D or the map.
- **Motion:** 120 / 200 / 400 ms on one easing curve (`cubic-bezier(0.2, 0.8, 0.2, 1)`), used only with a purpose. `prefers-reduced-motion` turns off pulses and camera movement.
- **Accessibility:**
  - text contrast ≥ 4.5:1;
  - hazards always have icon + label, never colour alone;
  - visible focus;
  - the map has a list alternative (`/zones`, the feed).
- **Anti-slop rules:**
  - no purple/blue gradients;
  - no emoji icons;
  - no "hero + three feature cards";
  - no filler copy;
  - real data on every screen;
  - no stock illustrations.

## 4. Pages
- **Landing `/`:**
  - **The model:** a sculpted 3D India. A build script downloads **AWS Open Data Terrain Tiles** (Terrarium PNG) and bakes one heightmap of India, masked to India's outline from our district geometry, into `public/landing/`. React Three Fiber renders it as a displaced, matte, stone-like relief with a rim light.
  - **Rivers:** Natural Earth (public domain), glowing cyan.
  - **Hazard glow:** live active zones glow as embers in their hazard colour, from `/map/zones`, with bloom.
  - **Scroll:** three camera beats: the whole country → the current worst hotspot → tilt to the horizon. Each beat shows one live number from `/stats/overview`.
  - **Copy:** one serif headline, one line, and one button, "Open the live map". The product name comes from config.
  - **Fallbacks:** a static poster image renders instantly; phones get a lighter model; reduced motion gets a still render.
- **App shell:**
  - an icon sidebar (Map, Zones, Ops; P4/P5 add more);
  - a top bar with the page title and a live status dot.
- **Map `/map`:**
  - a full-bleed MapLibre globe that flies to India, on a dark base style tuned to our tokens;
  - a hazard switch (Drought/Flood/Heat) and layer toggles;
  - **layers:** district tint (GeoJsonLayer), zone outlines (breathing/dashed), ColumnLayer extruded by score, signal dots (ScatterplotLayer; new ones pulse from SSE);
  - a collapsible live feed on the right;
  - clicking a zone opens a preview sheet → "Open zone".
- **Zones `/zones`:** a sortable, filterable table (hazard, status, type, score, sources, population, last seen).
- **Zone `/zones/:id`:**
  - an editorial header: serif name, hazard badge, status, ScoreMeter, population, trend sparkline, a mini map of the zone's outline;
  - **"Why this zone":** EvidenceQuote cards, the score breakdown (contribution per source plus indicator), and the trend chart;
  - Brief/Tenders/Community tabs are added only when P4/P5 build them.
- **Ops `/ops`:** stat tiles (posts today, analysed, active zones, tokens), a runs table, a rejection-reasons bar chart, and usage per LLM provider.

## 5. Testing and quality gates
- **Backend:**
  - a service/repository test against PostGIS plus an API test for each endpoint;
  - an SSE relay test (NOTIFY → event);
  - the OpenAPI → TypeScript type generation runs in the frontend build, so a contract mismatch fails `tsc`.
- **Frontend:**
  - Vitest + Testing Library for the patterns and hooks, with the API mocked by MSW;
  - Playwright end-to-end smoke tests against the real backend with a fixed fixture dataset: landing renders, map shows zones, the hazard switch changes layers, the zone page shows evidence, ops loads;
  - an axe-core accessibility scan on every page, failing on serious or critical issues.
- **Visual quality loop:**
  - Playwright screenshots of every page at 1440 px and 390 px;
  - each is reviewed against the `web-design-guidelines`, `design-taste-frontend` and `high-end-visual-design` skills and these rules;
  - fix and re-shoot until clean, and the user sees the final screenshots.
- **Budgets:**
  - initial JavaScript per route ≤ 250 KB compressed, excluding the lazy 3D and map chunks;
  - the landing poster visible in < 2 s;
  - the map stays smooth with all layers on.
- **Data:** development uses the real database contents; tests use fixtures.
