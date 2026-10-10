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
