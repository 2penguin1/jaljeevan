# Declaration Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily pipeline stage that finds state drought declarations in Indian news (GDELT) and in official PDFs linked from it. It loads talukas only under the safety rule: 1 official PDF, or 2 independent news sources.

**Architecture:**
- Pure list and state rules live in `domain/declaration_states.py`.
- A polite fetcher and the GDELT search live in `integrations/declaration_news.py`.
- `DeclarationWatchService` stores sources and mentions; `DeclarationPromoter` writes `drought_declarations`.
- A `watch` pipeline stage runs both. Results show on the ops page, and a review CLI exports what's waiting.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, PostGIS, httpx (`MockTransport` in tests), trafilatura, pdfplumber, rapidfuzz, stdlib `urllib.robotparser`; React 19 + Vitest for the ops box.

**Spec:** `docs/superpowers/specs/2026-10-11-declaration-watch-design.md`

**Execution note (ruling):** the user is away and delegated decisions, so the planner and the executor are the same session (native). Each task lists exact interfaces and test cases; the code is written under TDD against those tests rather than copied from this plan.

## Global Constraints

- Repositories never commit; services take their dependencies through constructors; `domain/` stays pure (no I/O).
- No captcha solving, no logins, no paywalls. Respect robots.txt. At most 1 request per second per host. HTML ≤ 2 MB, PDF ≤ 20 MB, and a PDF must start with `%PDF`.
- One GDELT query per run (`timespan=12w`, `maxrecords=75`), with backoff on HTTP 429.
- The stage runs at most once per 20 hours unless forced.
- Safety rule window: 120 days. Only mentions with score ≥ `TalukaMatcher.ACCEPT` (85) count. Independence means a different domain and a simhash Hamming distance above 8.
- Never overwrite an existing declaration from the last 120 days.
- Watch states: KA, TG→AP pool, AP, TN, GJ, RJ, MP, CT, UP, KL, HR, PB. Not watched: MH (official GR route) and BR, JH, OR, WB (block-level).
- New tables come from `create_all` (no schema patch is needed, since these are new tables).

## Review Focus

1. **A one-name sentence:** "Gadag taluk was declared drought-hit" names Gadag, so it must still count as a list, even with a single item.
2. **Unicode punctuation in lists:** a list joined with "&" or Unicode commas (`، ,`) and a trailing full stop must not keep the "." on the last name.
3. **Re-published URLs:** a URL already stored as `failed` with 2 attempts is never fetched again, even if GDELT returns it once more.
4. **Unknown page type:** a PDF link that returns HTML (an error page) → the source is `failed` and no mentions are stored.
5. **Duplicate words in a list sentence** ("Indi taluk" plus a later "Indi") → one mention per (source, taluka).

---

### Task 1: Domain — list sentences, hedges, states, more scripts

**Files:** Create `backend/app/domain/declaration_states.py`; modify `backend/app/domain/declarations.py` (`transliterate`). Test: `backend/tests/domain/test_declaration_states.py`, plus one Kannada case in `tests/domain/test_declarations.py`.

**Interfaces (produces):**
- `WatchState(code: str, pool: str, names: tuple[str, ...])`
- `WATCH_STATES: tuple[WatchState, ...]`
- `ListSentence(text: str, names: list[str])`
- `list_sentences(text: str) -> list[ListSentence]`
- `is_hedged(sentence: str) -> bool`
- `declares(sentence: str) -> bool`
- `names_state(text: str, state: WatchState) -> bool`
- `pick_state(counts: dict[str, tuple[int, int]], text: str) -> WatchState | None`, where `counts[code] = (accepted_matches, total_items)`

**Tests:**
- [ ] The Siasat sentence yields 40 names. The first is "Channapatna" and the last two are "Haliyal" and "Sirsi" (no "and", no trailing ".").
- [ ] "Gadag taluk was declared drought-hit." yields one name: "Gadag" (Review Focus 1).
- [ ] A heading line "The following taluks have been declared drought-hit:" followed by a line "Athani, Chikkodi & Raibag." yields three names (Review Focus 2).
- [ ] Hedges are rejected: "220 taluks may be declared drought-hit", "KPRS demands to declare Kalaburagi drought-hit: Afzalpur, Aland", "excluded talukas Karveer, Shirol" and the Lokmat demand line all yield nothing.
- [ ] `pick_state`:
  - KA (5 of 6) with "Karnataka" in the text → KA;
  - KA (5 of 6) without any KA name → None;
  - KA 3 vs AP 3 → None (below 60%);
  - KA 2 → None (below 3).
- [ ] `transliterate("ಗದಗ")` gives Latin text that `latin_key` matches to "Gadag" (≥ 85 with `TalukaMatcher`).
- [ ] Run `uv run pytest tests/domain -q`. Commit: "feat(watch): list sentences, hedges, watch states, Indic scripts".

### Task 2: Integration — GDELT declaration search and the polite fetcher

**Files:** Create `backend/app/integrations/declaration_news.py`. Test: `backend/tests/integrations/test_declaration_news.py`.

**Interfaces (produces):**
- `NewsHit(url, domain, title, published_on: date)`
- `DeclarationNewsSearch(client, sleep=time.sleep).search() -> list[NewsHit]`; raises `ExternalServiceError`
- `Fetched(url, content_type: str, body: bytes)`
- `FetchBlocked(Exception)` and `FetchFailed(Exception)`
- `PoliteFetcher(client, user_agent, clock=time.monotonic, sleep=time.sleep, min_interval=1.0, html_cap=2_000_000, pdf_cap=20_000_000).get(url, expect_pdf=False) -> Fetched`

**Tests (`httpx.MockTransport`):**
- [ ] Search parses artlist JSON into `NewsHit` (seendate `20261001T120000Z` → `date(2026,10,1)`), sends `timespan=12w`, and retries a 429 then succeeds, with the injected sleep called.
- [ ] Search raises `ExternalServiceError` after repeated 429s.
- [ ] robots.txt `Disallow: /` → `FetchBlocked`. A missing robots.txt (404) → allowed. robots.txt is fetched once per host.
- [ ] Two gets to the same host 0.2 s apart (fake clock) → sleep(0.8) is called; a different host → no sleep.
- [ ] A body over the cap → `FetchFailed`. `expect_pdf=True` with an HTML body → `FetchFailed` (Review Focus 4). A 500 response → `FetchFailed`.
- [ ] Run `uv run pytest tests/integrations/test_declaration_news.py -q`. Commit.

### Task 3: Models and repository

**Files:** Modify `backend/app/models/geo.py` and `backend/app/models/__init__.py`; create `backend/app/repositories/declaration_source_repository.py`. Test: `backend/tests/services/test_declaration_watch.py` (repository behaviour is covered through the service tests in Task 4, plus one direct test here).

**Interfaces (produces):**
- `DeclarationSource`: `url` (unique), `domain`, `kind`, `state_code`, `title`, `published_on`, `status`, `attempts`, `checked_at`, `list_fingerprint`.
- `DeclarationMention`: `source_id`, `area_id`, `score`, `severity`, `text`; unique on (source_id, area_id).
- `DeclarationSourceRepository(session)`:
  - `get_by_url(url) -> DeclarationSource | None`
  - `save(source) -> DeclarationSource` (flush)
  - `add_mentions(source_id, rows: list[dict])` (on conflict do nothing)
  - `counting(since: date, min_score: float) -> list[tuple[DeclarationMention, DeclarationSource]]`
  - `status_counts(since) -> dict[str, int]`

**Tests:**
- [ ] `add_mentions` with a duplicate (source, area) stores one row (Review Focus 5).
- [ ] Commit.

### Task 4: Service — watch and promoter

**Files:** Create `backend/app/services/declaration_watch.py` and `backend/app/services/declaration_promoter.py`. Test: `backend/tests/services/test_declaration_watch.py`.

**Interfaces:**
- **Consumes:** Tasks 1–3, `TalukaMatcher`, `AdminAreaRepository.talukas(state)`, `DeclarationRepository`, `TextFingerprinter`, and `pdf_lines` (from `app.cli.extract_declarations`; moved to `app/integrations/pdf_text.py` so services don't import a CLI).
- **Produces:**
  - `DeclarationWatchService(search, fetcher, sources_repo, areas_repo, fingerprinter, html_text=trafilatura_text, pdf_text=pdf_lines_from_bytes).run(now) -> dict`, with stats `{"hits", "new", "listed", "mentions", "by_status"}`.
  - `DeclarationPromoter(sources_repo, declarations_repo, fingerprinter).promote(now) -> dict`, with stats `{"declared": {state: n}, "waiting": n}`.

**Tests (test DB; fake search and fetcher returning fixture text):**
- [ ] One news source listing 4 KA taluks → 4 mentions; promote → 0 declared, 4 waiting.
- [ ] A second domain with a different sentence listing 3 of them → promote declares 3, with `order_ref` "news: 2 sources (severity not stated)" and `declared_on` = the earliest date.
- [ ] A second domain with the *same* sentence (a wire copy) → still 0 declared.
- [ ] An official PDF (.gov.in, kind official) listing 2 → 2 declared, `order_ref` "official order …", `source_url` = the PDF.
- [ ] A seen URL is not fetched again. A failed fetch is retried once on the next run, then never again (Review Focus 3).
- [ ] An article whose list is AP talukas but that names only Karnataka → `state_unclear`, no mentions.
- [ ] A taluka with an existing declaration within 120 days → not rewritten.
- [ ] Running the watch and the promoter twice → same rows.
- [ ] Commit.

### Task 5: Pipeline stage, container, CLIs

**Files:**
- Modify `backend/app/services/pipeline.py` (`DeclarationWatchStage`), `backend/app/core/container.py` and `backend/app/cli/run_pipeline.py` (skip choice `watch`).
- Create `backend/app/cli/watch_declarations.py` and `backend/app/cli/declaration_review.py`.

Test: `backend/tests/services/test_declaration_watch.py` (stage gap) and `backend/tests/services/test_pipeline*.py` (stage list).

**Interfaces:** `DeclarationWatchStage(watch, promoter, runs_repo, min_gap=timedelta(hours=20), force=False).run(ctx)`. It skips with `{"skipped": "ran <h>h ago"}` when the last run's stats contain a finished `watch` entry without an error inside the gap.

**Tests:**
- [ ] The stage skips inside 20 hours and runs after; an earlier errored run doesn't count.
- [ ] Review CLI: `rows_for_review(repo, since)` returns single-source and low-score rows in the `load_declarations` columns.
- [ ] Commit.

### Task 6: Ops read side and frontend box

**Files:** Modify `backend/app/schemas/read.py` (`DeclarationWatchInfo`), `backend/app/services/read_query_service.py` and `backend/app/core/container.py`; regenerate `backend/openapi.json` and `frontend/src/lib/api/schema.d.ts`; modify `frontend/src/features/ops/OpsPage.tsx` and `ops.test.tsx` (and the MSW fixture).

**Interfaces:** `DeclarationWatchInfo(last_checked: datetime | None, sources: dict[str, int], declared_by_state: dict[str, int], waiting: int)`; `OpsSummary.declarations: DeclarationWatchInfo | None = None`.

**Tests:**
- [ ] The API ops response includes `declarations`.
- [ ] Vitest: the "Declaration watch" region shows "Karnataka" and the waiting count.
- [ ] Run `npx tsc -b --noEmit`, `npx vitest run`, and `npm run build && npm run budgets`. Commit.

### Task 7: Docs, live run, final review

- [ ] Update CLAUDE.md commands, DECISIONS.md (simple points) and REMINDERS.md (out-of-scope items).
- [ ] Live run: `uv run python -m app.cli.watch_declarations --force` and report the numbers.
- [ ] Final whole-branch review by a fresh reviewer; fix Critical and Important findings test-first; run the full suite; commit.
