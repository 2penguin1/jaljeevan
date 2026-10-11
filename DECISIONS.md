# Decisions log

Simple notes on decisions Claude made for you, especially overnight. Newest at the bottom.
**Check:** if any line looks wrong to you, tell Claude and it will change it.

## 2026-10-11 (evening)
- **AI provider:** Groq (`openai/gpt-oss-120b`) is the main AI for now, as you chose. Claude on Bedrock is the backup, but it stays blocked until a card is added (see `REMINDERS.md`).
- **Paid scrapers:** Reddit uses `harshmaur/reddit-scraper` and X uses `kaitoeasyapi/...`, both charged per post. Each run is capped at about $0.20.
- **Jev (TypeSafe AI decision model):** not used for now. It is proprietary and only in early access. **Future idea:** try the open-source **Laya** as a cheap "is this post relevant?" gate before the AI. About 60% of posts the AI read were irrelevant, so this could cut AI cost and rate-limit pain. Try it only once there is a labelled test set to measure it.

## Overnight (P3 + fixes)
- **Groq ran out for today.** The free tier allows 200,000 tokens per day for this model, and we used it all. Its waits can be 12+ minutes, so Groq now **gives up after 60 seconds** and the next provider takes over.
- **Added Amazon Nova (on Bedrock) as the 2nd AI.** Order: **Groq → Nova → Claude**. Nova is Amazon's own model: it needs **no card**, it's paid from your AWS credits, and it stays inside AWS, which helps the "Built on AWS" score.
- **Nova Lite, not Nova Pro.** On 10 real posts, Lite kept 4/5 labels after the exact-quote check and Pro kept 5/5. But Lite is ~13× cheaper (about $0.0006 per batch of 10 posts), and you prefer low cost. To switch, set `NOVA_MODEL=apac.amazon.nova-pro-v1:0` in `backend/.env`.
- **Groq strict mode.** Groq must now use only allowed words (e.g. "town", never "city"). Before this, 150 posts failed because of a single off-list word in their batch.
- **P3 plan written and started without waiting for you**, because you asked me to finish P3 overnight. Plan: `docs/superpowers/plans/2026-10-11-p3-frontend.md` (14 tasks). I'm building it myself, task by task, then a fresh reviewer checks everything at the end.
- **The backlog is fully processed:** 257 posts classified and 0 failures (Nova handled all of it while Groq was out of quota). Zones now: 2 active, 24 watch.
- **P1 bugs fixed:**
  - neighbourhoods inside big cities (like Adyar, Chennai) now count as urban;
  - zones in "resolving" no longer flicker back to active;
  - two pipeline runs can't overlap (the second one skips);
  - Reddit asks only for last week's posts and drops anything older than 30 days before paying to store it.
- **New public read APIs** for the website: map layers, feed, zones, zone details, stats, ops. Plus a live stream that pushes new posts and zone alerts to the browser instantly.
- **Map: flat camera on the globe, no tilt.** The map library that draws our zones (deck.gl) can't follow a tilted globe: zones landed hundreds of km off. So the globe stays face-on. Score is shown by marker size instead of 3D columns. The landing page carries the 3D look.
- **Map library versions held back on purpose:**
  - MapLibre 5, not 6 (deck.gl doesn't support 6 yet);
  - deck.gl 9.3.11, not 9.4 (9.4 was published broken, with a missing file).
- **Country borders hidden on the map.** The base map's borders are not India's official ones, so the map hides them and our own district outlines draw India.
- **Tertiary text colour slightly brighter** than the design spec, so small grey text is readable (it now passes the 4.5:1 contrast rule).
- **The website (P3) is built:**
  - a 3D landing page;
  - a live map;
  - a zones list;
  - a zone page that explains "why this zone";
  - a pipeline health page.

  Open it with `cd frontend && npm run dev` while the API runs.
- **Landing page 3D:**
  - real terrain of India from AWS Open Data Terrain Tiles, cut to India's official outline from our own district data;
  - rivers from Natural Earth;
  - live zones glow as embers;
  - scrolling moves the camera: whole country, then the worst hotspot, then the horizon.

  A still image shows first, and is all that shows on devices without 3D support.
- **Only one button on the landing page** ("Open the live map"). It sits in the top bar, so it's reachable while you scroll.
- **Big numbers on the landing page use the serif font**, as the design spec asked. Smaller numbers in the app use the mono font.
- **The feed shows the newest *published* posts first.** Before this it used the order we collected them, so 9-day-old posts appeared above 12-hour-old ones.
- **Zones on the map show their score by marker size** (bigger = higher score), because the map can't tilt.
- **No shadcn UI kit yet.** Nothing in P3 needed it, and plain buttons plus our own small components cover it. It can be added when forms and dialogs arrive (tenders, CRM).
- **Speed:** each page loads at most about 125 KB of JavaScript first (the zone page about 224 KB because of the chart). The heavy 3D and map code loads after the page appears.
- **Tests:**
  - backend: 163 tests;
  - frontend: 33 unit tests;
  - 11 browser tests, which check every page plus an accessibility scan, on a separate test database (`jal_e2e`) so your real data is never touched.
- **Accessibility:**
  - every page passes an automatic accessibility scan;
  - zone names in the list are links, so a keyboard works too;
  - hazards always show an icon and a word, never colour alone.
- **Final check by a fresh reviewer (strongest model).** Verdict: good to merge after fixes. I fixed these, each with a test:
  - the live stream now reconnects by itself after the backend restarts (before, it could stay on "Reconnecting" forever), and it catches up on anything missed;
  - the feed no longer skips posts that share the same timestamp when you load older posts;
  - query strings now work on older Safari (before, the map would have shown errors there);
  - TypeScript strict checking is on;
  - the product name in the browser tab now comes from config, not hard-coded;
  - the map legend and landing text no longer state rules the code doesn't follow (zones can also be confirmed by an official source or a weather signal).
- **Small things left for later (not bugs a user will hit):**
  - the district tint can be up to 10 minutes stale after a run;
  - a few tiny cleanups (timers, caching, a line-ending settings file).
- **Branch not merged yet.** All P3 work is on `feat/p3-frontend` (nothing pushed, nothing deployed). Tell me "merge" and I'll merge it into `main` locally.

## Drought footprint (2026-10-11)
- **Drought is now decided by measured data, per taluka**, using the Government of India Drought Manual rules:
  - **Rain test:** a very dry last month (SPI −1 or below), or a severely dry last 3 months (SPI −1.5 or below).
  - **Soil test:** the Copernicus soil moisture anomaly.
  - **Official declarations** lift a taluka to at least the declared level.
- **News can no longer make a drought zone by itself.** "Solapur district" (one Times of India article) is gone. It became Akkalkot, Mangalvedhe, Sangole and Solapur South talukas.
- **Data alone gives "watch", not "active".** The Drought Manual asks for ground checks before declaring, so a zone goes active only when posts from that taluka confirm it, or the state has declared it. Dry talukas with no reports show as shading on the map, not as zones. (Before this, data alone made 1,144 active zones.)
- **People affected = people living in the dry parts of the taluka** (WorldPop 2025, about 1 km grid), split urban and rural. Every other zone also counts only people inside its own shape (fixes "a few Hyderabad colonies = all of Hyderabad").
- **Water supply is a new, 4th hazard** (violet). City tap and tanker complaints go there.
  - They count as drought evidence only in mostly rural talukas, where dry wells really follow the rain.
  - That's why Chennai is a water supply problem plus a "watch" drought, not an active drought.
- **Data sources:**
  - **Rainfall:** CHIRPS SPI (UCSB), every 5 days.
  - **Soil:** Copernicus GDO, every 10 days, about 3 weeks behind, so soil data up to 30 days old is still used.
  - **Population:** WorldPop 2025.
  - **Talukas:** geoBoundaries (6,810 matched to districts).
  - All free, no login. They're not on AWS; the daily refresh can run on AWS Lambda later.
- **IMD district rainfall is only a cross-check**, and it's ignored in a season's first 3 weeks. Right now the post-monsoon season started on 1 Oct, so every district reads −100%, which is meaningless.
- **Official declarations:** a new tool reads state orders.
  - Marathi taluka names are converted to English letters and matched, with unsure matches put on a list for you to check.
  - Severity words are translated by **IndicTrans2**, which runs locally. It needs your free Hugging Face token (see REMINDERS.md).
  - I could not download the Maharashtra order myself (its website has a captcha), so the declarations table is empty until you give me the PDF or the lists.
- **Bugs caught by running it on real data:**
  - Saving data for 6,800 talukas hit a database limit, so it now saves in batches.
  - Data alone was making active zones.
  - IMD's new-season numbers were wrong.
  - Chennai's tap complaints were turning it into a drought.

  Each one now has a test.
- **Speed:** a pipeline run takes about 30 seconds when the data hasn't changed, about 3 minutes when new rainfall/soil files arrive.

- **Final check by a fresh reviewer (strongest model):** "good to merge after fixes". I fixed each one with a test:
  - if a data source is down or late, drought zones are **held**, not closed, and the zone page says the data is out of date;
  - a taluka the state declared, but where the rain was normal, now shows its real population (not 0);
  - two talukas with the same name in different districts are never guessed: they go to your check list;
  - a zone that was confirmed earlier drops back to "watch" once its reports are older than 30 days and only data remains;
  - the cleanup of old drought zones never touches zones the government has **approved**;
  - the population overlay now uses about 100 MB of memory instead of about 1 GB (matters for AWS later).
- **Small things left for later:**
  - speeding up one database query when posts grow into the tens of thousands;
  - taluka-level flood/heat reports;
  - map shading refreshing instantly after new data (today, within 10 minutes);
  - a few tiny edge cases. All are listed in the notes.
- **Live result now:** 19 active and 15 watch drought zones, plus 22 water supply zones.
- **Branch:** all of this is on `feat/drought-footprint` (nothing pushed or deployed).
