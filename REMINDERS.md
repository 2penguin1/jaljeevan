# Reminders: things for you to do

Claude keeps this list up to date. Tick items off as you finish them.

## AWS / AI
- [ ] **Add a payment card to the personal AWS account (…8840)** so Claude works on Bedrock.
  - Console → **Billing and Cost Management → Payment preferences / Payment methods** → add a card. If AWS asks, upgrade the account from the free plan to the paid plan. Your $128 credits are still used first.
  - **Why:** AWS sells Claude through AWS Marketplace, and Marketplace needs a valid card even when credits pay. Today every Claude call fails with `INVALID_PAYMENT_INSTRUMENT`. (The Anthropic use-case form is already done.)
  - **Afterwards:** tell Claude. It will set `LLM_PROVIDERS=bedrock,groq` in `backend/.env`, so Claude becomes the main AI and Groq the backup, and re-test.
- [ ] **Optional:** set a $50 budget alert on account …8840 (Billing → Budgets) once the card is added.

## Security (after the hackathon)
- [ ] **Rotate the Apify API token** (apify.com → Settings → API & Integrations). It was pasted in chat.
- [ ] **Rotate the Groq API key** (console.groq.com → API Keys). It was pasted in chat.

## Quality
- [ ] **Label about 60 posts** for the accuracy check. Claude exports them with `uv run python -m app.evals.export --n 60`; you fill in the `expected` fields.

## Code
- [x] ~~Decide what to do with branch `feat/p1-backend`~~: merged into `main` on 2026-10-11.

## Later (planned at the end)
- [ ] **Redis:** add it at the end only if needed: caching (map layers, zone pages) or rate limits, mainly once more than one API server runs. Today Postgres and a small in-memory cache do these jobs.
- [ ] **S3:** switch on at deploy time (P2) for:
  - the raw post archive (set `RAW_BUCKET` in `backend/.env`; the code already supports it);
  - website files (served through CloudFront);
  - citizen photo uploads;
  - downloaded rainfall/soil files, if we want to keep them.
- [ ] **RAG** (search our own documents and give the AI the right pieces before it writes):
  - relief briefs grounded in the Drought Manual and past similar zones;
  - an "ask the data" chat for officials;
  - long-term plans that cite official guidance;
  - summaries and insights generated from collected posts.

  Use pgvector inside our Postgres, so no new server. Not part of the current drought work.
