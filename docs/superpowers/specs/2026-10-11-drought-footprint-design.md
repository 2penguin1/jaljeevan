# Spec: data-driven drought footprint, water-supply hazard, real population (sub-project 1), Taxonomy v2 and reservoirs (later)

> Approved by the user on 2026-10-11 (plan mode). Sub-projects 2 and 3 get their own specs before they are built.

## Context
**The problems you spotted.**
- Drought zones come from news: a single Times of India article made **"Solapur district"** an active drought zone, counting the **whole district** (14.5 lakh people).
- Drought really hits some talukas and villages, so any tanker or budget calculation built on that number would be badly wrong.
- **Fine zones overcount too.** A few Hyderabad colonies counted as all of Hyderabad (69.9 lakh), because population is the sum of full gazetteer places.
- **City tap-water complaints (Delhi, Chennai) show up as drought.** The taxonomy tags `SUPPLY` as `[drought]`.
- **The taxonomy is thin:** 8 L1 categories and 23 L2 labels, with no need type, water source, affected group or quantities.

**Outcome.** Drought is decided by **measured data**, following the Government of India Manual for Drought Management:
- the unit is the **taluka**, and the rainfall test is **SPI ≤ −1** (moderate) or **≤ −1.5** (severe);
- posts only **confirm and pinpoint** impact;
- "people affected" counts only the people living in the stressed area (WorldPop ~1 km grid), split urban and rural;
- city supply failures become their own hazard, **Water supply**.

The UI label is always **"Indicative drought footprint (GoI Drought Manual, rainfall trigger + soil moisture anomaly)"**. Official state declarations appear alongside.

Spec docs to write first (brainstorming → spec → writing-plans, per CLAUDE.md):
- `docs/superpowers/specs/2026-10-11-drought-footprint-design.md`
- `docs/superpowers/specs/<date>-taxonomy-v2-design.md`

## Verified data sources
| Use | Source | Notes |
|---|---|---|
| Rainfall trigger | **CHIRPS v3 preliminary SPI**, 6-pentad (≈1 month) and 18-pentad (≈season) | `data.chc.ucsb.edu/products/SPI/CHIRPS3/`<br>0.05°, every 5 days, ~2 days behind<br>CC BY, no login, ~66 MB per file |
| Population | **WorldPop 2025 India, 1 km constrained** | 16 MB GeoTIFF, CC BY |
| Talukas | **geoBoundaries IND ADM3** (simplified) | 6,836 sub-districts, ODbL |
| Official cross-check | **IMD district departure** (761 districts) | Read from IMD's rainfall map page<br>Fragile, so a cross-check only |
| Declarations | **Maharashtra GR, 25 Sep 2026** (265 talukas)<br>**Karnataka** (177 taluks, 2 Oct) | Hand-transcribed CSV |
| Soil moisture (impact) | **Copernicus GDO Soil Moisture Index Anomaly** (`smang`), behind a swappable port | Standardized anomaly; ≤ −1 means drier than normal (baseline 1995–2023)<br>0.05°, the same grid as CHIRPS<br>Every 10 days, ~1–10 days behind, CC BY, no login<br>About 18 MB per India crop<br>Not on AWS |

Ruled out for the live layer:
- **ERA5 on AWS:** about 3 months behind, and no climatology.
- **GRACE drought indicators:** about 3 months behind.
- **SPEI Monitor:** the latest data needs a licence.

Fallback on AWS: **NASA SMAP L4** (Earthdata Cloud, us-west-2, ~2.5 days behind, free login). It needs its own climatology built from 2015 onward, so it stays a later option.

CHIRPS SPI files are uncompressed strips, so India is **one ranged GET of ~18 MB**: rows 38N–6N, starting at byte 8 + row × 28,800. There's no need to download the full 66 MB.

## Step 0: write future reminders (first thing after approval)
Add a **"Later (planned at the end)"** section to `REMINDERS.md`, in simple points:
- **Redis:** add it at the end, if needed, for caching (for example map layers and zone pages) or rate limits, mainly when we run more than one API server.
- **S3:** turn it on at deploy time (P2) for:
  - the raw post archive (set `RAW_BUCKET`);
  - the website files (with CloudFront);
  - citizen photo uploads;
  - kept rainfall and soil files, if wanted.
- **RAG** (searching our own documents to give the AI context) for:
  - writing relief briefs grounded in the Drought Manual and past similar zones;
  - an "ask the data" chat for officials;
  - long-term plans that cite official guidance;
  - generating summaries and insights from collected posts.

  Use pgvector inside our Postgres, so no new server.
- **RAG is not in this plan.** It's a reminder for later only.

Commit this together with the spec docs.

## Sub-project 1: drought footprint (four slices; each ships with tests)

### Key decisions
- **Schema changes.** A new `app/core/schema_patches.py` holds idempotent SQL (`ADD COLUMN IF NOT EXISTS`, ...). It runs inside `init_db()` after `create_all` (`app/core/database.py`). The repo has no migrations today, and Alembic isn't worth it for this.
- **Water hazard.** Key `water`, label "Water supply", a violet token (`--water`), lucide `Droplet`. `SUPPLY` is tagged `[water]` only.
- **Drought zones come only from the data footprint** (`HazardPolicy.zoning = "footprint"`). Posts tagged drought or water that fall inside a flagged taluka add evidence. Flood, heat and water keep post-driven zoning (`"posts"`, the current logic).
- **Talukas are stored as `admin_areas.level='subdistrict'`**, with `parent_id` pointing to the district.
- **New tables** (created automatically):
  - `area_indicators(area_id, period, source, metric, value)`, a long table so new metrics need no ALTER;
  - `drought_declarations`.
- **Zones gain** `area_id` (stable taluka identity, with a unique index on hazard + area) and `population_urban`.
- **Population lives in one place:** a `PopulationGrid` port backed by WorldPop. It's used for every zone of every hazard, with the gazetteer as fallback. That fixes the root cause in `ZoneDetectionService._population`.
- **People affected in a drought taluka** = people in grid cells where SPI ≤ −1, not the whole taluka. It's computed at indicator refresh as the metrics `pop_stressed` and `pop_stressed_urban`.
- **Raster stack:** `rasterio` + `numpy` only. Zonal statistics use our own small helper; skip `exactextract`.
- **`DroughtRules` is a pure, versioned module** (`RULES_VERSION`). Data severity becomes the existing `boost`, posts combine through the existing noisy-OR (`ZoneScorer.score`), and the state machine and alerts stay unchanged.
- **IMD is a cross-check only**, never a trigger.

### Slice A: water-supply split
1. **Add `schema_patches.py`**, hooked into `init_db`, with patches for:
   - `zones.area_id` and `zones.population_urban`;
   - the unique index on hazard + area;
   - widening `signal_locations.precision` to `varchar(16)`.

   Update the models in `app/models/intel.py` to match. Test that running the patches twice is harmless.
2. **Backend hazard.**
   - `app/domain/taxonomy.py:9` `HAZARDS` += `"water"`; `app/data/taxonomy.yaml` gets `SUPPLY → [water]` and a broader description.
   - `app/domain/hazards.py`: add `WaterPolicy` and a `zoning` attribute on every policy.
   - `IndicatorRepository.latest_by_district(None)` returns `{}`.
   - One `Hazard = Literal[HAZARDS]` in `app/schemas/read.py`, imported by `api/v1/endpoints/map.py` and `read.py`.
   - Update the prompt wording in `app/domain/classification.py`.
   - **New CLI** `app/cli/retag_hazards.py` recomputes `signals.hazards` from the stored `l1_codes`, with no LLM calls.
3. **Frontend hazard.**
   - Regenerate the OpenAPI types; `src/lib/api/types.ts` derives `Hazard` from the schema.
   - `src/lib/hazards.ts`: add `water`; `isHazard` becomes `HAZARD_LIST.includes`.
   - `tokens.css`: add `--water`.
   - `LandingPage.useEmbers` uses `useQueries` over `HAZARD_LIST`.
   - The e2e fixture gains a water zone, and the smoke test exercises it.

### Slice B: real population for every zone
4. **Population port.**
   - Add `rasterio` and `numpy`. **First step:** confirm `uv add rasterio` imports on Windows with Python 3.13; fall back to 3.12.
   - New `app/integrations/raster.py` (`Grid`, `read_window`, `zonal_mean` with a point fallback for tiny polygons, `coverage_sum` on a 10× finer grid for fractional pixels).
   - `app/integrations/population.py` `WorldPopGrid`: urban means at least 1,500 people per km²; a missing file fails soft.
   - `PopulationGrid` and `PopulationCount` in `ports.py`; a `worldpop_path` setting.
5. **Zone detection.**
   - `ZoneDetectionService` accepts `population=`. `_population(wkt, area_ids, evidence)` tries the grid first (source `worldpop`), then the gazetteer, then reported numbers.
   - Wire it in `core/container.py`.
   - Add `population_urban` and `population_source` to `ZoneSummary` and the read/map repositories.
   - The zone page says "People living in zone area (WorldPop 2025): urban x / rural y".
   - Tests cover the Hyderabad-colonies case and the no-grid fallback.

### Slice C: drought footprint
6. **Talukas.**
   - `GeoSeedService.load_subdistricts`.
   - `AdminAreaRepository.has_level`, `link_subdistricts` (parent district via `ST_PointOnSurface`) and `geometries(level)`.
   - In `seed_geo.py`, the subdistrict layer gets its own idempotent guard.
   - `GazetteerResolver` falls back from district to subdistrict, so "Mohol taluka" resolves.
7. **`app/domain/drought.py`.**
   - Holds `DroughtRules`, `DroughtInputs`, `DroughtAssessment` (level, reasons, boost), the pentad helpers and `FOOTPRINT_LABEL`.
   - Levels: none, watch, moderate, severe.
   - Declarations lift a zone to at least the declared level; data older than 20 days counts as unknown.
   - **First step:** check the manual's wording ("any of" vs "deficit AND dry spell").
   - Table-driven tests, one per rule case.
8. **Tables and repositories:** `AreaIndicator` and `DroughtDeclaration` models, plus `AreaIndicatorRepository` (`upsert_many`, `latest_period`, `latest`, `freshness`) and `DeclarationRepository`.
9. **Data refresh.**
   - `app/integrations/chirps.py` `ChirpsSpiSource`: parse the directory listing for the latest pentad, read the India window into memory. **First step:** inspect one real file for nodata, scale and dtype.
   - `app/services/indicator_refresh_service.py`: if the pentad is new, compute per taluka `spi_6p`, `spi_18p`, `pop_stressed` and `pop_stressed_urban` (SPI ≤ −1 mask × population grid), then upsert. Otherwise skip as fresh. One source failing doesn't stop the others.
   - A new `IndicatorStage` in `services/pipeline.py` runs after ingest (savepoint-isolated); the CLI gains `--skip indicators`.
   - **Later, in P2:** a daily EventBridge → Lambda job runs just this stage.
10. **IMD cross-check:** `app/integrations/imd.py` parses the amCharts `areas` array and fails soft. It writes daily through the existing `IndicatorRepository.upsert(..., "imd", rainfall_departure_pct=...)` and records matched and unmatched counts.
11. **Declarations, extracted from source documents.**
    - **Where:** `app/cli/extract_declarations.py` builds `app/data/declarations/2026_kharif.csv`. Then `app/cli/load_declarations.py` loads it into `drought_declarations` and prints any unmatched names.
    - **Maharashtra** (Marathi GR PDF), one step per stage:
      1. Pull text with `pdfplumber`. If the Devanagari comes out garbled (old font encodings), OCR the pages locally with Tesseract and its `mar` language pack.
      2. Transliterate the names to Latin script with `indic-transliteration`. This is a pure-Python library with no model; taluka names are proper nouns, so they need transliteration, not translation.
      3. Fuzzy-match within the right district against geoBoundaries taluka names with `rapidfuzz`.
      4. Matches at or above a confidence cut-off are accepted. Matches below it go to a "check me" CSV that **you review**.
    - **Karnataka:** the lists are already English (press releases), so they go straight to matching.
    - **Local translation with AI4Bharat IndicTrans2 (your decision: included and built):**
      - `app/integrations/indictrans.py` `IndicTranslator` sits behind a `Translator` port in `ports.py`. It uses the distilled model `ai4bharat/indictrans2-indic-en-dist-200M` through Hugging Face `transformers`, plus the `IndicTransToolkit` pre/post-processor.
      - It runs **locally on CPU**: about 1 GB to download once, cached under `~/.cache/huggingface`, and loaded lazily only when the extract CLI runs.
      - **What it translates:** the GR's sentences and table headers, for example the order title, the severity words ("गंभीर" = severe, "मध्यम" = moderate) and the declaration date. The extractor can then read severity and the order reference reliably.
      - **What it doesn't translate:** taluka names. Those still go through transliteration plus fuzzy match, because a translation model can change proper nouns.
      - **Dependencies** go in an optional group, `[project.optional-dependencies] indic = ["torch", "transformers", "IndicTransToolkit", "sentencepiece"]`. Normal installs, tests and the API stay light. Install with `uv sync --extra indic`.
      - **First step:** confirm that torch CPU and `IndicTransToolkit` install on this Windows machine with Python 3.13. Fall back to Python 3.12 in a separate venv just for the extractor, or run it in WSL.
      - **Tests:**
        - unit tests use a `FakeTranslator`, with no model download;
        - one opt-in test marked `@pytest.mark.slow` (skipped unless `RUN_SLOW=1`) translates a real Marathi sentence and checks that key English words appear.
    - **Tests:** fixture snippets in Devanagari and garbled-font text, the transliteration-plus-match table, severity extracted from translated text, and the low-confidence routing.
12. **Footprint zoning.**
    - `app/services/drought_assessor.py` (`DroughtAssessor.assess`) is shared by zone detection, the map and the zone page, so all three always agree.
    - `ZoneRepository`:
      - `_ELIGIBLE` takes a hazard array (`s.hazards && :hzs`);
      - `area_evidence`: points inside the taluka count fully, taluka mentions count fully, district mentions count ×0.5;
      - `area_zone`, `dismiss_legacy`, and `set_shape_from_area`.
    - `ZoneDetectionService._footprint_zones` creates a zone when the level is moderate or worse, or watch with posts, or the taluka is declared:
      - `zone_type="taluka"`, name "Mohol taluka, Solapur";
      - population = `pop_stressed`;
      - boost from the assessment.
      - When the data clears, the zone may move to resolving.
    - Legacy district-wide drought zones are dismissed.
    - Tests:
      - the Solapur case: an article alone creates no zone;
      - Mohol with SPI −1.7 plus a post creates a taluka zone;
      - a Delhi tap complaint becomes a water zone only;
      - zone identity stays stable across runs;
      - a zone resolves when the data clears;
      - a taluka that's only declared still gets a zone.
13. **API and UI.**
    - `ZoneDetail.drought`, a `DroughtPanel` with SPI, soil moisture, people in stressed areas, the IMD cross-check, declared status, reasons and the label. `zone_detail` takes the boost from the assessment, so the score maths is correct.
    - `GET /map/footprint?hazard=drought` returns flagged talukas, cached. A footprint layer in `layers.ts` shades by level and dashes the outline when declared.
    - New `src/features/zones/DroughtPanel.tsx` (plain DOM, no charts, to stay inside the budget).
    - The ops page shows data freshness; the e2e fixture gets a taluka plus indicators plus a declaration.

### Slice D: soil moisture (impact indicator; in sub-project 1, as you chose)
14. **Soil moisture.**
    - A `SoilMoistureSource` port, with `app/integrations/soil.py` `GdoSoilMoistureAnomaly`. It finds the latest dekad file and reads only the India rows with one ranged GET (nodata is 1e20; ocean is NaN).
    - The refresh service writes the metric `soil_anomaly` per taluka, with a freshness guard.
    - In `DroughtRules`, soil class is ≤ −1 moderate and ≤ −1.5 severe, the same scale as SPI.
    - The manual's soil measure is a percentage (PASM/MAI). The rule module's docstring records the mapping we chose, and the label says "soil moisture anomaly".
    - Data older than 20 days counts as unknown.
15. **Docs:** CLAUDE.md commands (`retag_hazards`, `load_declarations`, `--skip indicators`, subdistrict and WorldPop seeding), the seed README rows, and DECISIONS.md.

### Risks
- **"Built on AWS" for the data:** the rainfall and soil sources aren't on AWS. We keep only derived values in our database (raw files optionally in S3), and the daily refresh runs on AWS Lambda in P2. NASA SMAP (on AWS) is the AWS-hosted soil option if needed.
- **GDO per-dekad files** sit on an unofficial mirror with occasional gaps. We fall back to the official yearly NetCDF.
- **OCR of Marathi PDFs** can misread names. The confidence cut-off routes doubtful rows to you; nothing is guessed silently.
- **IndicTrans2 is heavy** (torch, ~1 GB model). It's kept in an optional install group and used only by the offline extract CLI, never by the API or pipeline, so the app and the AWS Lambdas stay small.
- **rasterio on Windows:** checked first, with a Python 3.12 fallback.
- **CHIRPS layout:** pinned in a test fixture from one real file.
- **Sources going down:** freshness checks keep the last good values, and ops plus the panel show stale data.
- **IMD scrape breaking:** fail-soft, cross-check only.
- **Declaration names not matching:** unmatched names are printed, never guessed.
- **Too many taluka zones:** watch-level talukas with no posts show only in the footprint layer.

## Sub-project 2: Taxonomy v2 (separate spec; after sub-project 1)
- **New per-post fields.** All are required (Groq strict mode), with synonym-coercing list validators that drop unknown values rather than fail the batch:
  - `setting` (urban, peri-urban, rural);
  - `need_types` (drinking water, tanker, food, fodder, shelter, medical, cooling, evacuation, sanitation, power);
  - `water_sources` (piped, tanker, borewell, handpump, open well, surface, reservoir, canal, packaged);
  - `affected_groups`;
  - `quantities[{text, kind}]`.
- **Quantities are verbatim spans.** `app/domain/quantities.py` parses them in code: Indian digit grouping, lakh/crore, ₹, number words. `EvidenceValidator` drops any span that isn't verbatim in the post.
- **Richer YAML (about 10 L1, 38 L2):**
  - new L1 `WATER_QUALITY` (contamination, fluoride/arsenic/salinity);
  - SUPPLY: rationing, fetching from far;
  - AGRI: sowing delay, irrigation failure, fodder camps;
  - FLOOD: flash flood or cloudburst, infrastructure damage, crop damage;
  - HEAT: night heat, livestock, power cuts;
  - RELIEF: camps.
  - `PROMPT_VERSION` becomes p2.
- **A sharper water-vs-drought split.** `derive_hazards` uses `water_sources` and `setting`: a rural borewell or well post counts as water plus drought; a city piped-supply post counts as water only.
- **Storage:** `signals.meta["facts"]`.
- **Batch size and backfill.** Batch size becomes a setting (6 for Groq's tokens-per-minute limit). `app/cli/reclassify.py` backfills, and runs only after evals pass.
- **Evals.** Build a stratified 80-post export; a second model proposes labels and **you confirm them**. Metrics gain set-F1 for needs, sources and groups, hazard accuracy, and quantity F1.
- **UI:** a `FactChips` component on evidence quotes and feed items; `top_needs` per zone, counted in code.

## Sub-project 3: reservoir levels (outline)
1. Parse the CWC weekly bulletin PDF with `pdfplumber`.
2. Geolocate reservoirs from a hand-made CSV.
3. Compute storage as % of the 10-year normal and store it in `area_indicators` (source `cwc`).
4. `DroughtRules` adds the hydrology impact using the 2020 combination rule.
5. Show nearby reservoirs in the drought panel.

## Verification (each slice)
- **Backend:** `cd backend && uv run pytest -q`. New tests:
  - domain rule tables;
  - synthetic GeoTIFF zonal-statistics tests;
  - service tests on PostGIS (Solapur, Mohol, Delhi tap, Hyderabad population);
  - idempotent schema patches.
- **Contract:** `uv run python -m scripts.export_openapi`, then in `frontend/` run `npm run gen:api` and `npx tsc -b --noEmit`.
- **Frontend:** `npx vitest run`, `npm run build && npm run budgets` (≤ 250 KB per route).
- **End to end:** `npx playwright test smoke a11y`, with the fixture extended for water, taluka, indicators and a declaration.
- **Live check on the dev DB:**
  1. `retag_hazards`;
  2. seed talukas and WorldPop;
  3. `run_pipeline --skip ingest`;
  4. confirm "Solapur district" is gone, flagged talukas appear with stressed-population numbers, and Delhi/Chennai taps are under Water supply;
  5. compare against the MH/KA declared lists (agreement rate in ops).
- **Visual:** screenshots at 1440 and 390 px; the hazard switch fits four options.
