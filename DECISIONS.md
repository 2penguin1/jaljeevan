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
