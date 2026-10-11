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

## Past drought orders (2026-10-11)
- **We don't solve the government site's captcha automatically.** It's the site's way of blocking bots; getting around it breaks their rules and could get us blocked. Instead:
  - **New orders:** the site's open "latest orders" page has direct PDF links with no captcha. A watcher can pick them up (not built yet; ask when you want it).
  - **Past orders:** a temporary helper opens a normal browser and fills in the search, then **you** type the captcha (about 10 seconds) and it downloads every drought order PDF.
- **Drop folder:** any order PDF put in `backend/app/data/declarations/inbox/` is read and loaded by one command, then moved to `processed/`. Orders that aren't about drought go to `skipped/`.
- **Severity:** read straight from the Marathi words (गंभीर = severe, मध्यम = moderate), no translator needed. If an order doesn't say, the taluka is loaded as "moderate", the lowest declared level, and the order note says "severity not stated".
- **Broken PDF letters:** Maharashtra's PDFs often come out with wrong letters (शिरूर becomes जशरूर, सांगोला becomes सांर्ोला). The matcher repairs these two patterns automatically, and keeps the original spelling too, so real names aren't damaged.

- **First real order loaded (26 Sep 2026, 265 talukas):** 230 matched automatically and loaded; 20 doubtful names are in `backend/app/data/declarations/MH_202609261117494941_check.csv` for you to look at. The rest were too badly broken by the PDF to read safely.
- **How I checked that the 230 are right:** the order lists how many talukas each district has. No district got more matches than the order lists, so no wrong taluka slipped in at the district level. I also read every match with a low score by hand.
- **What made matching accurate on this order:**
  - more broken-letter repairs seen in this order: ध written as र्, श written as ि, हिं written as सह;
  - the district and division columns of the table ("6 नाशिक 10", a lone "ठाणे") are no longer read as talukas;
  - a name that exists in two districts (Malegaon, Ashti, Kalamb) is settled by the names around it in the same row; otherwise it goes to your check list;
  - renamed places are known: Dharashiv = Osmanabad, Chhatrapati Sambhajinagar = Aurangabad, Ahilyanagar = Ahmednagar;
  - the order's way of writing suffixes is known: "उ. सोलापूर" = Solapur North, "नागपूर शहर" = Nagpur (Urban);
  - two different talukas that read equally well are never guessed; they go to the check list.
- **Only real declarations load talukas.** An order now has to *declare* drought ("दुष्काळ जाहीर" / "declared drought"). The 22 Sep order that only set up a ministers' committee had loaded 3 wrong talukas; I removed them and that order is now skipped.
- **Live result now:** all 230 declared talukas are active drought zones (245 active in total), plus 22 water supply zones.

## Declaration watch: drought declarations of other states from the news (2026-10-11)
You asked me to decide the rest myself and build it. My decisions, in simple points:
- **How it finds them:** once a day, GDELT (a free world news index) is searched for "declared drought-hit … taluks / mandals / tehsils" in Indian news. Each new article is read once. If it links to an official government PDF (.gov.in / .nic.in), that is read too.
- **Only real declarations count.** I checked real articles first. Lokmat's headline said "19 talukas declared" but the list was only *demanded*; The Hindu wrote "may be declared". So names are taken only from a sentence that itself declares, and words like demand, may, likely, seek, excluded or मागणी cancel it.
- **Safety rule (as you approved):** a taluka is declared only when **one official order**, or **two independent news sites**, name it within 120 days. Independent means a different website **and** different wording: the same news-agency (ANI) story copied onto five websites counts once. www. and m. versions of a site count once.
- **Which state:** the names must mostly match one state's talukas, and the article must name that state. Otherwise the article is skipped; names are never guessed.
- **States watched:** Karnataka, Telangana, Andhra Pradesh, Tamil Nadu, Gujarat, Rajasthan, Madhya Pradesh, Chhattisgarh, Uttar Pradesh, Kerala, Haryana, Punjab.
  - **Maharashtra is left out** on purpose: its official order site is better, and we already read it.
  - **Bihar, Jharkhand, Odisha and West Bengal are left out:** they declare by block, a smaller unit than our talukas.
- **Never overwrites:** if a taluka already has a declaration this season (for example from the Maharashtra order), the news never changes it.
- **Being polite to websites:** we obey each site's robots.txt, make at most 1 request per second per site, refuse very large files, and use no logins, captchas or paywalls. GDELT is asked once per run and the watch runs at most once every 20 hours.
- **When things fail:** a failed article is tried once more the next day, then left. If GDELT is down, the run notes it and the rest of the pipeline carries on.
- **What you see:** the ops page has a new "Declaration watch" box (articles read, talukas declared per state, talukas waiting). `uv run python -m app.cli.declaration_review` writes the waiting talukas to a CSV for you to check and load.
- **English only for now.** Hindi, Kannada and Telugu news are noted in reminders.
- **Small fix on the way:** Kannada, Telugu, Tamil, Gujarati, Punjabi and Malayalam letters can now be read in official orders (same method as Marathi).
- **An official order is dated by its own text.** A 2026 article that links a 2023 order cannot make it count as this year. An order with no date in it counts only like one news site.
- **One-taluka news** counts only when the article names a single watched state and the name matches a taluka there (still needs a second site, like everything else).
- **Same publisher, different sub-site** (kannada.news18.com and news18.com) counts as one website.
- **If GDELT refuses us** (it rate-limits hard), the watch tries again after 2 hours, not on every pipeline run.
- **First live run (today):** 75 articles found and read politely.
  - 1 article had a real list (Siasat: the 40 taluks Karnataka added on 1 Oct). 34 of the 40 match our taluk map; 5 are new taluks our older map does not have.
  - 53 articles talk about drought but give no names; 7 had lists that were not declarations (for example "left off the list", a demand letter) and were correctly skipped; 10 could not be downloaded (ANI blocks robots, one site rate-limited us). They get one retry tomorrow.
  - **Nothing declared yet, on purpose:** only one website printed the names, and the rule needs two. 35 Karnataka talukas now wait; they are on your review list (`declaration_review`).
- **Final check by a fresh reviewer:** it found one serious problem (a single broken PDF could stop the whole watch and make it re-download everything on every run) and five important ones (listed above as fixed). All fixed, each with a test. Left for later (small): names with initials like "H.D. Kote" can cut a list short (missed names, never wrong ones); checking where a link redirects to before we deploy on AWS.

## Deployed on AWS (2026-10-11, evening)
- **Live site:** https://d77gmqy6y3kav.cloudfront.net (Mumbai region, account ending 8840).
- **Built as code** with AWS CDK (`infra/`). One command deploys and one removes it.
- **What runs where:**
  - website: S3 + CloudFront;
  - API: ECS Fargate behind a load balancer;
  - database: RDS PostgreSQL with PostGIS, in a private network only the API can reach;
  - pipeline: twice a day (05:30 and 17:30 IST), started by EventBridge;
  - keys: Secrets Manager;
  - AI: Amazon Bedrock (Nova Lite) as a fallback after Groq;
  - raw posts: archived in S3.
- **Cheaper choices:**
  - no NAT gateway (saves about $35 a month); the database stays private anyway;
  - one container image for both the API and the pipeline;
  - no Step Functions; a scheduled task does the same job today.
- **Data:** the local database (all zones, declarations, drought data, posts) was copied up once. From now on the cloud pipeline adds new data by itself.
- **Cost:** about $60–65 a month from the $128 credits. Remove it after judging.

## Relief tenders (lean vendor / government CRM, 2026-10-11 night)
- **The flow:**
  1. Zone page → "Drinking water needed from tankers". The number is computed in code, with the formula shown: rural people × share on tankers × 20 L a day.
  2. Create a tender: the price is prefilled from nearby vendors' median.
  3. Invited vendors are ranked by distance, price, fleet size and reliability, each with a plain reason.
  4. Vendors accept, counter or decline, and the government answers.
  5. A bar shows how much water is committed.
- **No logins tonight.** A "Viewing as" switch lets one person play both sides for the demo. Because the site is public, every change needs the demo access code (the admin token in `backend/.env`); reading stays open.
- **No AI here:** every number is arithmetic in code.
- **All 16 vendors are invented demo businesses** and are labelled "(demo)".
- **Left for later:** real accounts and roles, email or app notifications to vendors, NGO campaigns, long-term plans.

## Full CRM, end to end (2026-10-11, late night)
You asked me to decide and build it all. In simple points:
- **Real logins replace the demo switch.**
  - Passwords are stored only as bcrypt hashes.
  - Your session is a signed token in a cookie that page scripts cannot read.
  - Only citizens can sign up themselves, and always as "citizen". Officer, vendor and NGO accounts are given out by us.
  - Five wrong passwords in a minute from one place pause that place, not the real user.
- **Demo accounts** (the password is `DEMO_PASSWORD` in `backend/.env`; it is also in Secrets Manager):

  | Email | Role |
  |---|---|
  | `officer@relief.demo` | Relief officer |
  | `akkalkot@vendor.demo`, `solapur@vendor.demo`, `latur@vendor.demo` | Tanker vendors |
  | `ngo@relief.demo` | NGO |

- **Negotiation:**
  - Who acts is decided by the account. A vendor can only answer its own bid.
  - Messages in each bid thread; "raise price" for every open bid.
  - If two people act at once, one wins and the other is asked to reload.
  - **Bids are confidential:** the public sees the tender and the invited vendors, but only the officer and that vendor see the offers and messages.
- **Vendor inbox:** needs your answer / waiting for the government / closed.
- **Notifications:** a bell with private alerts. A new tender goes to the invited vendors, a reply goes to the other side, and pledges and sign-ups go to the NGO. Email through AWS SNS is left for later, because every address must click a confirmation link.
- **AI relief brief:**
  - The AI writes only words: a short situation summary, and actions picked from a fixed list.
  - Code computes every number (people, kL a day, trips, price, budget) and removes any sentence in which the AI put a number.
  - The officer approves or rejects. Approving publishes the tender.
- **NGO side:** campaigns with pledges (promises only, no money is taken) and volunteer tasks with limited places.
- **Long-term plans:**
  - Options come from a fixed menu.
  - Quantities and costs are computed in code from the zone size. They are clearly labelled **indicative**, because the unit costs are demo assumptions, not official rates.
  - The AI writes the title and summary (no numbers). The officer approves, and there is a printable one-pager.
- **Two fresh security reviews** were done. Every serious finding was fixed with a test: the double-action race, locking people out, "infinite" numbers, long passwords, and inputs echoed back in errors.
