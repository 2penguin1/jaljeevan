# Reminders: things for you to do

Claude keeps this list up to date. Tick items off as you finish them.

## AWS / AI
- [ ] **Add a payment card to the personal AWS account (…8840)** so Claude works on Bedrock.
  - Console → **Billing and Cost Management → Payment preferences / Payment methods** → add a card. If AWS asks, upgrade the account from the free plan to the paid plan. Your $128 credits are still used first.
  - **Why:** AWS sells Claude through AWS Marketplace, and Marketplace needs a valid card even when credits pay. Today every Claude call fails with `INVALID_PAYMENT_INSTRUMENT`. (The Anthropic use-case form is already done.)
  - **Afterwards:** tell Claude. It will set `LLM_PROVIDERS=bedrock,groq` in `backend/.env`, so Claude becomes the main AI and Groq the backup, and re-test.
- [ ] **Optional:** set a $50 budget alert on account …8840 (Billing → Budgets) once the card is added.

## Translation model (for Marathi drought orders)
- [ ] **Unlock the IndicTrans2 model on Hugging Face** (free). Claude can't do this for you:
  1. Make a free account at huggingface.co.
  2. Open https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M and accept AI4Bharat's terms.
  3. Settings → Access Tokens → create a **Read** token.
  4. Put it in `backend/.env` as `HF_TOKEN=...` (never in chat). Then tell Claude.
  - **Why:** the model is "gated", so it only downloads after you accept its terms. Until then, drought orders still work through name matching, and only the sentence translation waits.

## AWS deploy
- [ ] **Remove the AWS stack after judging** so credits are not used up: `cd infra && npx cdk destroy --profile spice` (about $60–65/month while it runs). The database leaves a final snapshot; delete it in the RDS console if not needed.
- [ ] **After rotating the Groq / Apify keys**, update `backend/.env` and run `cd backend && uv run python ../infra/scripts/put_app_secret.py`, then restart the API service (ECS → service → Force new deployment).

## Security (after the hackathon)
- [ ] **Rotate the Apify API token** (apify.com → Settings → API & Integrations). It was pasted in chat.
- [ ] **Rotate the Groq API key** (console.groq.com → API Keys). It was pasted in chat.

## Quality
- [ ] **Look at 20 doubtful taluka names** from the 26 Sep drought order: `backend/app/data/declarations/MH_202609261117494941_check.csv`. Delete rows that are wrong; to correct one, type the right taluka name and empty its `area_id`. Then, from `backend/`: `uv run python -m app.cli.load_declarations app/data/declarations/MH_202609261117494941_check.csv`.
- [ ] **Label about 60 posts** for the accuracy check. Claude exports them with `uv run python -m app.evals.export --n 60`; you fill in the `expected` fields.

## Code
- [x] ~~Decide what to do with branch `feat/p1-backend`~~: merged into `main` on 2026-10-11.
- [x] ~~Branches `feat/p3-frontend` and `feat/drought-footprint`~~: merged into `main` on 2026-10-11 (local only, nothing pushed).

## Later (planned at the end)
- [ ] **Redis:** add it at the end only if needed: caching (map layers, zone pages) or rate limits, mainly once more than one API server runs. Today Postgres and a small in-memory cache do these jobs.
- [ ] **S3:** switch on at deploy time (P2) for:
  - the raw post archive (set `RAW_BUCKET` in `backend/.env`; the code already supports it);
  - website files (served through CloudFront);
  - citizen photo uploads;
  - downloaded rainfall/soil files, if we want to keep them.
- [ ] **Speed up the drought evidence query** before posts reach tens of thousands (it can't use the map index today; split it into three simpler queries).
- [ ] **Flood and heat reports at taluka level:** posts like "flood in Mohol taluka" only count for drought today.
- [ ] **Instant map shading after new data:** today the dry-taluka shading can lag up to 10 minutes after a refresh (clear the map cache at the end of each pipeline run).
- [ ] **Small edge cases** from the final review (listed in `DECISIONS.md`): very small city talukas with no 1 km grid square, list lines like "X district: A, B" in English orders, orders that mention both "moderate" and "severe", and a few safety caps (download size limit, checking the model's remote code).
- [ ] **RAG** (search our own documents and give the AI the right pieces before it writes):
  - relief briefs grounded in the Drought Manual and past similar zones;
  - an "ask the data" chat for officials;
  - long-term plans that cite official guidance;
  - summaries and insights generated from collected posts.

  Use pgvector inside our Postgres, so no new server. Not part of the current drought work.

## Declaration watch (news, other states) — left for later
- [ ] **Check the news review list** now and then: `uv run python -m app.cli.declaration_review`, then load what is right with `load_declarations`. Talukas named by only one news site wait there.
- [ ] **New taluks missing from our map data** (e.g. Karnataka's Harohalli, Kalasa, Kushalnagar, Ullal, Byndoor): they cannot be matched until newer taluk boundaries are loaded.
- [ ] **Hindi, Kannada and Telugu news** are not searched yet (English only).
- [ ] **Bihar, Jharkhand, Odisha, West Bengal** declare drought by block; they need block boundaries first.
- [ ] **State revenue websites** could be read directly for one or two states (stronger than news), if those states matter.
- [ ] **Review buttons in the app** (accept / reject on the ops page) instead of the CSV.

## Relief tenders — left for later
- [ ] Real logins and roles (government, vendor, NGO) instead of the "Viewing as" switch and the shared demo code.
- [ ] Notify invited vendors (SNS email or in-app) and real vendor onboarding; the 16 vendors are demo data.
- [ ] Delivery tracking (trips done vs promised) and vendor reliability updated from it.

## Full CRM — left for later
- [ ] **Email alerts through AWS SNS** for vendors and officers (each address must confirm once). Ask before sending to real addresses.
- [ ] **Change the demo password** after judging: edit `DEMO_PASSWORD` in `backend/.env`, run `put_app_secret.py`, then re-run the seed task (it rotates existing accounts).
- [ ] **Real unit costs** for long-term plans (state schedule of rates) instead of the indicative demo numbers in `backend/app/domain/plan_menu.py`.
- [ ] Password reset by email, and an admin screen to add officer/vendor/NGO accounts (today they come from the seed).
- [ ] Live push for notifications (today the bell checks every 15 seconds).
