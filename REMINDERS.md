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

## Security (after the hackathon)
- [ ] **Rotate the Apify API token** (apify.com → Settings → API & Integrations). It was pasted in chat.
- [ ] **Rotate the Groq API key** (console.groq.com → API Keys). It was pasted in chat.

## Quality
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
