# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is an India water-crisis intelligence platform (drought, flood, heat) for the WeMakeDevs × AWS Environmental Hacks hackathon (Heat and Water track, ends 2026-10-11). **"Jal" is only the folder name.** The product name is undecided, so keep it in a single config string and don't hard-code it.

The backend follows the approved **class-based layered LLD** in [docs/superpowers/specs/2026-10-11-backend-lld.md](docs/superpowers/specs/2026-10-11-backend-lld.md): `domain/` stays pure, services take dependencies through their constructors, repositories never commit, and design patterns are used only where they solve a real need.

The approved design is [docs/superpowers/specs/2026-10-10-mvp-design.md](docs/superpowers/specs/2026-10-10-mvp-design.md). It covers scope, AWS architecture, schema, the intelligence-layer robustness rules and the build order. Read it before building anything. Add **Commands** and **Architecture** sections here once code exists.

Standing decisions:
- **AWS account:** the personal free-plan account ending **8840**, reached through the CLI profile **`spice`** (IAM user `sujal-test`, AdministratorAccess), in region **ap-south-1** (Mumbai). It has $128 of free credits until 2027-01-06. **Never use the CLI `default` profile (account ending 9175). It is the user's OFFICE account and is off-limits.** Always pass `--profile spice`, or set `AWS_PROFILE=spice`, already in `backend/.env`.
- **LLM (current):** **Groq `openai/gpt-oss-120b` is the main AI**, as the user chose on 2026-10-11, with Claude on Bedrock as the fallback (`LLM_PROVIDERS=groq,bedrock`). Claude is blocked by `INVALID_PAYMENT_INSTRUMENT`: AWS Marketplace needs a card on the free-plan account. Once the user adds a card, switch to `LLM_PROVIDERS=bedrock,groq`. Open user to-dos are in [REMINDERS.md](REMINDERS.md); mention them when relevant.
- **LLM (Bedrock details):** Claude **Haiku 4.5** on Bedrock through the India inference profile `in.anthropic.claude-haiku-4-5-20251001-v1:0`, verified working on 2026-10-10. Haiku 5.5 is blocked on the free plan. Use the legacy `AnthropicBedrock` client, because Mantle IDs don't cover inference profiles. Don't send `output_config.effort`, because Haiku 4.5 rejects it. The model is a config value, so switching back to 5.5 means changing `CLASSIFY_MODEL`/`BRIEF_MODEL`.
- **Secrets:** they live only in git-ignored `backend/.env` locally, and move to Secrets Manager when deployed (P2). Never commit or echo them. The Apify token was pasted in chat on 2026-10-11; remind the user to rotate it after the hackathon.
- **The AI writes the words; code does the arithmetic.** Every number in briefs and plans comes from code.
- **Evidence quotes must be verbatim substrings** of the source post.
- **AWS:** the services listed in the spec. Redis, SES and a second Step Functions machine were deliberately dropped; the spec says why.

## Commands

Run these from `backend/` unless noted.
- **Database:** `docker compose up -d db`, from the repo root. PostGIS runs on host port **5433**, because a local PostgreSQL already owns 5432. Tests use the database `jal_test`; development uses `jal`.
- **Install:** `uv sync`
- **All tests:** `uv run pytest -q`
- **One test:** `uv run pytest tests/services/test_zone_detection.py::test_hazards_are_kept_separate -q`. Tests live in `tests/{domain,services,integrations,api}`.
- **Load geography (one-time, ~6 min):** `uv run python -m app.cli.seed_geo`. Data files go in `app/data/seed/`; that folder's README lists the download URLs.
- **Pipeline once:** `uv run python -m app.cli.run_pipeline`. Options: `--skip ingest|classify|geocode|zones` and `--no-locator`.
- **API:** `uv run fastapi dev` (entrypoint `app.main:app`). Admin routes `/admin/pipeline/*` need the header `X-Admin-Token`.
- **Evals:**
  - `uv run python -m app.evals.export --n 60`, then hand-label the output into `app/evals/gold.jsonl`;
  - then `uv run python -m app.evals.run`.
- **OpenAPI for the frontend:** `uv run python -m scripts.export_openapi` writes `backend/openapi.json`. Then, in `frontend/`, run `npm run gen:api` to regenerate the TypeScript types.

Frontend (run from `frontend/`; the backend API must be on :8000 for dev):
- **Install / dev:** `npm install`, then `npm run dev` (http://localhost:5173; `/api` is proxied to :8000, so there's no CORS).
- **Unit tests:** `npx vitest run` (Vitest + Testing Library + MSW). **Types:** `npx tsc -b --noEmit`.
- **Build + budgets:** `npm run build && npm run budgets` (each route's first-load JS must stay ≤ 250 KB gzip).
- **End-to-end + accessibility:** `npx playwright test smoke a11y`. It seeds the separate `jal_e2e` database (`backend/scripts/seed_e2e.py`), starts the API on :8100 and `vite preview` on :4173.
- **Screenshots for visual review:** `SCREENS=1 npx playwright test screens` writes to `e2e/screens/` at 1440 and 390 px.
- **Landing 3D assets:** `npm run bake` rebuilds `public/landing/*` from AWS Terrain Tiles, our district outline and Natural Earth rivers. The output is committed, so only re-run it if the inputs change.

## Architecture (frontend)

- One Vite + React 19 + TypeScript app. Routes are lazy (`src/app/router.tsx`):
  - `/` landing;
  - `/map`, `/zones`, `/zones/:zoneId`, `/ops`, inside `AppShell` (icon sidebar, top bar with the live dot).
- **Data flow:** pages → feature components → TanStack Query hooks (`src/lib/hooks/queries.ts`) → `apiGet` (`src/lib/api/client.ts`, the only `fetch`). Types are generated from OpenAPI (`src/lib/api/schema.d.ts`). The map's GeoJSON types are hand-written in `types.ts`.
- **Live updates:** `AppShell` holds ONE `EventSource` (`LiveProvider`). Pages subscribe with `useLiveSubscription`. Events invalidate the matching query keys.
- **Design tokens** live in `src/design/tokens.css` (CSS variables plus Tailwind v4 `@theme`). Shared UI is in `src/components/patterns/`. There's no shadcn yet: nothing in P3 needed Radix.
- **Heavy WebGL stays out of first load:**
  - `features/map/GlobeMap.tsx` (MapLibre 5 globe + deck.gl 9.3) and `features/landing/Scene.tsx` (three.js) are lazy chunks;
  - `layers.ts` is a pure function, unit-tested without WebGL;
  - the globe camera stays flat (deck.gl's GlobeView can't follow pitch or bearing).
- **Pinned on purpose:**
  - `maplibre-gl@5` (deck.gl 9.3 reads `map.transform`, which v6 removed);
  - `@deck.gl/*@9.3.11` plus `overrides` for `@loaders.gl/*@4.5.3` (9.4.0 was published with a missing dependency);
  - TypeScript 5.9 (openapi-typescript needs it).

## Architecture (backend)

Layers, per the LLD:
- `api/` controllers call services, which use `domain/` (pure rules), `repositories/` (SQL) and `integrations/` (vendors, through `integrations/ports.py`).
- `core/container.py` is the composition root. App-scoped singletons are attributes; anything that needs a Session is built by factories such as `container.pipeline(session)`.
- `Container.run_pipeline_job()` is the entry point: one `session_scope()` transaction, then `EventBus.dispatch()` after commit. Only one run at a time: a second one records `{"skipped": ...}`.
- **Public read API** (`/api/v1`, no auth):
  - map GeoJSON comes from `MapRepository`/`MapQueryService`, with the district layer cached for 10 minutes;
  - the feed, zones, zone detail (evidence plus score arithmetic), stats and ops come from `ReadRepository`/`ReadQueryService`;
  - `/api/v1/live` is SSE, fed by `LiveEventRelay`: one Postgres `LISTEN` per process fans out to per-client queues.

The pipeline (`services/pipeline.py`) runs these stages in order:
1. **`IngestStage`:** fetchers, `IngestionService`, weather.
2. **`ClassifyStage`:** `ClassificationService` sends batches of 10 to Bedrock; `EvidenceValidator` keeps only verbatim quotes.
3. **`GeocodeStage`:** a `ResolverChain` of `GazetteerResolver` then `LocatorResolver`, run in two passes.
4. **`ZoneStage`:** `ZoneDetectionService` does PostGIS clustering, stable zone identity, `ZoneScorer`, `HazardPolicies` and `ZoneStateMachine`, and raises `ZoneEscalated` events.

Known limits:
- Social sources use paid pay-per-result Apify actors (Reddit is `harshmaur/reddit-scraper`, about $2.2 per 1,000 posts; X is `kaitoeasyapi/...`, about $0.25 per 1,000 posts). Per-run caps keep a run at roughly $0.2; the user's Apify balance is about $8.
- District populations are undercounted until a Census CSV is added.

## References

[docs/references/](docs/references/) holds resources the user shares: hackathon rules, prior projects to borrow from, and data sources. Read the relevant file before designing or building. When the user shares a new link or repo, condense it into a new file there.

## Workflow: always go through the planning skills

Use the installed skills for every piece of work, and invoke each one before acting, including before clarifying questions. Default pipeline:

1. **`superpowers:brainstorming`**: for any new idea, feature or change in behaviour. It narrows scope and produces an approved design. For a hackathon, push hard on what the demo actually needs and cut everything else.
2. **`superpowers:writing-plans`**: turns the approved design into small, ordered tasks before any code is written.
3. **`superpowers:subagent-driven-development`** (or `superpowers:executing-plans` when working inline): carries out the plan.
4. **`superpowers:test-driven-development`** while implementing, and **`superpowers:systematic-debugging`** for any bug or failure.
5. **`superpowers:verification-before-completion`** before claiming anything works. Run it and show the output.

Alternatives (these overlap with the pipeline above, so pick one per task and don't stack them):
- **`spec-driven-development`**: use when you want lasting `requirements.md` / `design.md` / `tasks.md` docs, for example for judges or teammates.
- **`claude-mem:make-plan`** then **`claude-mem:do`**: a phased plan executed by subagents, as an alternative to steps 2–3.

UI work: **`frontend-design:frontend-design`** and **`ui-ux-pro-max:ui-ux-pro-max`**. Code review before submission: **`superpowers:requesting-code-review`** / **`code-review`**.

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance

- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->
