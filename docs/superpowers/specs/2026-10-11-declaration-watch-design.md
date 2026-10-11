# Declaration watch: official drought declarations from the news (design)

Date: 2026-10-11. Status: approved in chat (approach A and Parts 1–3). The user then asked me to make the remaining decisions and build it; those decisions are marked **Decision** below and logged in DECISIONS.md.

## Goal

Find state drought declarations (lists of taluks, mandals or tehsils) for states other than Maharashtra, every day, without anyone downloading anything. A taluka loads into `drought_declarations` only when the evidence is strong enough. Everything else waits, or goes to a review list for a person.

**Success:** a live run picks up Karnataka's lists from news (for example the 1 Oct 2026 Siasat list of the 40 added taluks). It loads only what the safety rule allows. The ops page shows what was found and what is waiting. Tests cover the rule without touching the internet.

## Findings from a live probe (2026-10-11) that shape the design

1. **GDELT works as discovery.** A 12-week query over Indian outlets returns 75 relevant articles with real publisher URLs. Note: `timespan=3months` silently returns nothing; `12w` works. GDELT also rate-limits hard (HTTP 429), so we need backoff and at most one query per run.
2. **Names live in one sentence.** Siasat writes "The 40 taluks added in the latest phase are Channapatna, …, Haliyal and Sirsi." Most articles give only counts. The existing prose extractor would lose the first and last names ("…are Channapatna", "Haliyal and Sirsi"), so we need a dedicated list reader.
3. **Headlines and demands mislead.** Lokmat's headline says "19 talukas declared", but the body lists 19 talukas whose declaration is only *demanded*. The Hindu writes "may be declared". So a list counts only when its own sentence (or the heading line right before it) declares, and contains no hedge (demand, may, likely, seek, excluded, protest, मागणी …).
4. **Wire copies are not independent.** One ANI story appears on aninews.in, prokerala.com, webindia123, indiagazette and calcuttanews. Two sources count as independent only if they are different domains **and** their list sentences are not near-duplicates (simhash).
5. **No article linked an official PDF.** Following .gov.in/.nic.in PDF links is still built, because it's the strongest evidence when it does appear, but news is the main route.
6. **Boundary data:** KA has 227 taluks loaded (the newer set). Telangana mandals are stored under `state_code='AP'` (geoBoundaries predates 2014).

## Rules

- **Which states:** KA, TG (matched in AP's pool), AP, TN, GJ, RJ, MP, CT, UP, KL, HR, PB.
  - **Decision:** Maharashtra is excluded, because the official GR route (inbox) is authoritative there and its news is mostly Marathi demand coverage.
  - **Decision:** Bihar, Jharkhand, Odisha and West Bengal are excluded, because they declare by block, which isn't our unit.
- **Article state:** for each configured state, match the list items against that state's talukas. The state with the most accepted matches wins, but only if:
  - it has at least 3 accepted matches;
  - at least 60% of the matched items belong to it;
  - its name (or an alias, such as "K'taka" or "Ktaka") appears in the article.

  Otherwise the article is skipped as "state unclear".
- **List sentence:** a sentence or line that contains a declaration cue (declared, added, included, brought under, drought-hit list, notified, जाहीर, घोषित) and no hedge cue. The names are the text after "are", "is", "include", "including", "namely" or ":", split on commas, semicolons, "and" and "&".
- **Safety rule (promotion):** a taluka in a configured state is declared when, within the last 120 days, it is named by either:
  - **one official PDF** (a .gov.in or .nic.in document); or
  - **two independent news sources**, meaning different domains with list sentences that aren't near-duplicates (simhash Hamming distance above 8, the same threshold as `TextFingerprinter`).

  Only mentions with match score ≥ `TalukaMatcher.ACCEPT` count.
- **Written once per season:** if the taluka already has any declaration in the last 120 days (from any route, including the Maharashtra GR), nothing is written. Otherwise a row is inserted with:
  - `declared_on` = the earliest counting mention's date;
  - severity = `severity_from_text` of the list sentence, or else moderate with "(severity not stated)" in `order_ref`;
  - `order_ref` = "official order" or "news: N sources";
  - `source_url` = the official PDF if there is one, otherwise the first news URL.
- **Review list:** `app.cli.declaration_review` writes a CSV in the `load_declarations` format (with `area_id`) containing:
  - single-source talukas;
  - mentions scoring between `REVIEW_FROM` (70) and `ACCEPT`.

  The person edits it and loads it with the existing loader.

## Politeness and failure handling

- **Requests:** one GDELT query per run, with backoff on 429. Each article site gets a robots.txt check (stdlib `urllib.robotparser`, cached per host) and at most 1 request per second per host. Our existing User-Agent is sent. Responses are streamed with size caps (HTML 2 MB, PDF 20 MB), and a PDF must start with `%PDF`.
- **Source status:** each article or PDF gets one `declaration_sources` row whose status is one of `listed`, `no_list`, `not_declaration`, `state_unclear`, `failed` or `blocked`.
  - A `failed` source is retried on the next run, up to 2 attempts in total.
  - `blocked` means robots.txt disallows the page; it is never fetched.
- **Run frequency:** the stage runs at most every 20 hours, based on the last finished watch recorded in `pipeline_runs` stats. If GDELT fails, the stage records the error and the pipeline continues; existing declarations are untouched.

## Components (layers per the LLD)

- **`domain/declaration_states.py`** (pure): `WatchState` (code, pool state code, names and aliases); `WATCH_STATES`; `list_sentences(text)`, which yields (sentence, names); `is_hedged`.
- **`domain/declarations.py`:** `transliterate` learns the Kannada, Telugu, Tamil, Gujarati, Gurmukhi and Malayalam scripts, for official PDFs.
- **`integrations/declaration_news.py`:** `DeclarationNewsSearch`, the GDELT artlist query for declarations, returning `NewsHit(url, domain, title, published_at)`; and `PoliteFetcher`, which handles robots, per-host rate, size caps and the PDF magic check, and returns `Fetched(url, content_type, body)` or raises `FetchBlocked` / `FetchFailed`.
- **Models (`models/geo.py`, created by `create_all`):**
  - `DeclarationSource`: id, url (unique), domain, kind (`news`/`official`), state_code, title, published_on, status, attempts, checked_at, list_fingerprint (bigint).
  - `DeclarationMention`: id, source_id, area_id, score, severity, text, unique on (source_id, area_id).
- **`repositories/declaration_source_repository.py`:** `seen_urls`, `retryable`, `save_source`, `add_mentions`, `counting_mentions(since)`, `pending(since)`, `summary(since)`.
- **`services/declaration_watch.py`:** `DeclarationWatchService.run(now)` → stats. It searches, then for each hit: skip seen URLs → fetch → extract text (trafilatura for HTML, `pdf_lines` for PDFs) → check for a declaration → find list sentences → pick the state → store the source and its mentions. Official PDF links found in an article are queued as `official` sources.
- **`services/declaration_promoter.py`:** `DeclarationPromoter.promote(now)` applies the safety rule and writes through `DeclarationRepository`.
- **`services/pipeline.py`:** `DeclarationWatchStage` (name `watch`), placed after `indicators` and before the zone stage; it is wired in `core/container.py`.
- **Read side:** `OpsSummary.declarations: DeclarationWatchInfo` (last run, sources by status, loaded by state, waiting for a second source, to review), shown in a "Declaration watch" box on the ops page.
- **CLIs:** `app.cli.watch_declarations` (run once, with `--force` to ignore the 20-hour gap) and `app.cli.declaration_review`.

## Testing

- **Domain:**
  - list-sentence extraction (the Siasat sentence; "X and Y"; colon lists);
  - hedge rejection (Lokmat, "may be declared", "demands", "excluded");
  - the state-pick rule;
  - transliteration for Kannada.
- **Integration:**
  - `PoliteFetcher` on `httpx.MockTransport`: robots disallow → blocked; the size cap; non-PDF bytes; per-host waits through an injected clock;
  - GDELT query parsing and 429 backoff.
- **Service (PostGIS test DB):**
  - one news source → waits;
  - two independent domains → declared;
  - two domains with the same wire text → waits;
  - one official PDF → declared;
  - the wrong state or an unclear state → no mentions;
  - running twice changes nothing;
  - a failed fetch is retried once, then left;
  - an existing Maharashtra-style declaration is never overwritten.
- **Ops API:** the declarations block appears. **Frontend:** the ops box renders (Vitest + MSW).
- **Live:** one real run at the end, with the result reported.

## Out of scope (in REMINDERS)

- Hindi, Kannada or Telugu news queries.
- Block-level states.
- Per-state official site scrapers.
- A review UI with accept and reject buttons.
