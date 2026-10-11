# Drought Footprint (sub-project 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline; the author is the executor). Every task is red → green → commit.

**Goal:** drought zones decided by measured data per taluka (CHIRPS SPI + GDO soil-moisture anomaly), people counted from the WorldPop grid, city supply failures as a separate "water" hazard, IMD cross-check, and official declarations (extracted with local tools + IndicTrans2).

**Spec:** `docs/superpowers/specs/2026-10-11-drought-footprint-design.md` (approved). Backend rules: `docs/superpowers/specs/2026-10-11-backend-lld.md`.

## Spike results (2026-10-11) — rulings that adjust the spec
- `rasterio 1.5.2` (GDAL 3.12) + `numpy 2.5` install and import on Windows / Python 3.13. No Python downgrade needed.
- CHIRPS SPI files: 7200×2400 float32, uncompressed one-row strips, origin (−180, 60), 0.05°, NaN = ocean, no nodata tag. Live check: Mohol SPI-18p = −2.73, Lucknow +0.94, 15.8% of India land ≤ −1.
- GDO soil anomaly (`smang`): 7200×3000 float32, origin (−180, 90), 0.05°, nodata 1e20. The mirror lags (latest dekad 11 Sep on 11 Oct). **Ruling:** soil data may be up to 30 days old (SPI stays 20), and the panel shows the date.
- **Ruling: download the whole file to a temp dir, read the India window with rasterio, then delete it** (not hand-written HTTP range reads). The layouts differ (CHIRPS IFD at end, GDO at start); full downloads are about 1 GB/month total; it's far less code.
- geoBoundaries IND ADM3 simplified: 6,822 polygons, property `shapeName`, via `media.githubusercontent.com` (the repo files are LFS pointers). Saved as `app/data/seed/india_subdistrict.geojson`.
- WorldPop 2025 1 km: 3504×3451, EPSG:4326, nodata −99999, total 145.7 crore people. Saved as `app/data/seed/ind_pop_2025_CN_1km_R2025A_UA_v1.tif`.
- IndicTrans2: `IndicTransToolkit` needs **`transformers<5`**. The model `ai4bharat/indictrans2-indic-en-dist-200M` is **gated on Hugging Face**, so the user must accept its terms and set `HF_TOKEN`. The code reads the token from settings; tests use a fake translator.

## Tasks (in order; files per task; tests named)
1. **Schema patches.**
   - Code: `app/core/schema_patches.py` (+ the hook in `database.init_db`). Models: `Zone.area_id`, `Zone.population_urban`, a partial unique index, `SignalLocation.precision` String(16).
   - Test: `tests/test_schema_patches.py` (apply twice; columns exist).
2. **Water hazard (backend).**
   - Taxonomy: `taxonomy.py` HAZARDS; `taxonomy.yaml` SUPPLY → [water].
   - Policies: `hazards.py` WaterPolicy + a `zoning` attribute; `IndicatorRepository.latest_by_district(None)` returns {}.
   - Types and prompt: `schemas/read.py` Hazard from HAZARDS (used in `map.py` and `read.py`); prompt wording.
   - CLI: `cli/retag_hazards.py`.
   - Tests: update the existing hazard tests, plus water API tests, the retag CLI test, and a water zone from a SUPPLY cluster.
3. **Water hazard (frontend).**
   - Code: types from the schema; `hazards.ts`; the `--water` token; `useEmbers` via `useQueries`.
   - Fixtures: seed_e2e water zone; smoke test for water.
   - Tests: vitest, tsc, e2e.
4. **Raster helpers + PopulationGrid.**
   - Code: `integrations/raster.py` (Grid, read_window, zonal_mean with point fallback, coverage_sum); `integrations/population.py` WorldPopGrid; ports `PopulationGrid`/`PopulationCount`; settings `worldpop_path`; deps rasterio + numpy.
   - Tests: `tests/integrations/test_raster.py` and `test_population.py` on synthetic GeoTIFFs.
5. **Population in zone detection.**
   - Code: `_population` grid-first; container wiring; read/map fields `population_urban`/`population_source`; ZonePage copy.
   - Tests: Hyderabad case, district zone via grid, no-grid fallback.
6. **Talukas.**
   - Code: `load_subdistricts`; `AdminAreaRepository.has_level`/`link_subdistricts`/`geometries`/`wkt`; seed_geo guard; resolver subdistrict fallback.
   - Tests: linking, resolver (Mohol → subdistrict, Barmer → district).
7. **DroughtRules** (`domain/drought.py`).
   - Covers: pentad and dekad helpers, the level table, stale data, the declaration lift, and FOOTPRINT_LABEL.
   - Test: `tests/domain/test_drought.py`.
8. **Tables + repositories.**
   - Models: `AreaIndicator`, `DroughtDeclaration`.
   - Repositories: `AreaIndicatorRepository`, `DeclarationRepository`.
   - Tests: upsert idempotency, latest pivot, freshness.
9. **Sources + refresh stage.**
   - Sources: `integrations/chirps.py`, `integrations/soil.py` (download → temp → window).
   - Service: `services/indicator_refresh_service.py` (spi_6p, spi_18p, soil_anomaly, pop_stressed, pop_stressed_urban); `IndicatorStage`; `--skip indicators`.
   - Tests: listing parse, fake sources, freshness skip, failure isolation.
10. **IMD cross-check.**
    - Code: `integrations/imd.py` (parse + fail-soft); daily write via `IndicatorRepository.upsert`.
    - Tests: fixture parse, unmatched counted, malformed → [].
11. **Declarations.**
    - Code: `integrations/indictrans.py` (Translator port, lazy, HF_TOKEN); `domain/declarations.py` (transliterate, severity from translated text, fuzzy match); `cli/extract_declarations.py`; `cli/load_declarations.py`; optional dep group `indic`; deps `indic-transliteration`, `rapidfuzz`, `pdfplumber`.
    - Tests: fake translator, Devanagari match table, low-confidence routing, loader matching. The slow real-model test is opt-in.
12. **Footprint zoning.**
    - Code: `services/drought_assessor.py`; ZoneRepository `_ELIGIBLE` array, `area_evidence`, `area_zone`, `dismiss_legacy`, `set_shape_from_area`; `ZoneDetectionService._footprint_zones` + `data_cleared`.
    - Test: `tests/services/test_drought_footprint.py` (Solapur, Mohol, Delhi tap, stable identity, resolves, declared-only, legacy dismissed).
13. **API + UI.**
    - Backend: `ZoneDetail.drought` panel; zone_detail boost from the assessment; `GET /map/footprint`; ops freshness.
    - Frontend: footprint layer; `DroughtPanel.tsx`; ops table; e2e fixture.
    - Checks: vitest/tsc/e2e/budgets.
14. **Docs + live check.** CLAUDE.md commands, seed README, DECISIONS.md, REMINDERS (HF token). Live run on the dev DB per the spec's verification.
