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
- [ ] **Decide what to do with branch `feat/p1-backend`:** merge into `main`, open a PR (needs a GitHub repo), or keep it as is.
