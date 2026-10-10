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
