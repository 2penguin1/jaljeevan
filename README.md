# JalJeevan

**A live, honest picture of India's water crisis**: drought, floods, heat and water-supply failures. JalJeevan takes officials from the first signal to a water tanker on the ground.

**Live:** https://d77gmqy6y3kav.cloudfront.net  ·  Track: **Heat and Water** (WeMakeDevs × AWS Environmental Hacks)

---

## The problem

Every summer, India's water crisis shows up first in the news, on social media and in government orders, long before it reaches an official spreadsheet. These signals are scattered across sources, written in many languages, and noisy. On top of that, "the whole district is in drought" overstates the need, which breaks tanker and budget planning.

## What JalJeevan does

- **Collects signals twice a day.** It reads news (GDELT, RSS), Reddit and X posts, CHIRPS satellite rainfall, Copernicus soil moisture, and official state drought orders, including Marathi PDFs with broken fonts.
- **Understands them.** An AI model labels each post by hazard, and every evidence quote is checked word for word against its source.
- **Places them on a map.** Each post is located among about 6,800 talukas.
- **Scores zones.** Zones are scored per taluka, so officers see the worst places first on a live map (light and dark themes).
- **Keeps drought numbers honest.** Drought follows the Government of India Drought Manual: a rainfall trigger, soil moisture and official declarations. "People affected" counts only those living in the dry grid cells, based on WorldPop.
- **Turns information into relief:**
  - **Relief briefs.** The AI writes the words; code computes every number (litres, tanker trips, budget). An officer approves the brief, and approval publishes a tender.
  - **Tanker tenders.** The nearest reliable vendors are invited and negotiate privately (accept, counter, decline, message). A bar tracks how much water has been committed.
  - **Community.** NGOs run pledge campaigns (pledges are promises, not payments) and volunteer tasks with limited places.
  - **Long-term plans.** Plans use options from a fixed menu, with quantities and indicative costs computed per zone. They can be printed as a one-pager.
- **Accounts and roles.** Relief officers, tanker vendors and NGOs use seeded accounts; citizens can sign up themselves. Sessions use secure httpOnly cookies, and each person gets private notifications.

## Architecture

```
Sources (GDELT, RSS, Reddit, X, CHIRPS, Copernicus, state orders)
   └─► Pipeline (EventBridge → ECS Fargate task, twice a day)
         ingest → indicators → declaration watch → AI classify → geocode → zones
   └─► RDS PostgreSQL + PostGIS
   └─► FastAPI on ECS Fargate (behind an ALB)  ◄── CloudFront /api/*
   └─► React app on S3                         ◄── CloudFront /
```

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, TypeScript, TanStack Query, Tailwind v4, MapLibre + deck.gl globe, three.js 3D terrain |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2, GeoAlchemy2, PostGIS, rasterio, pdfplumber, rapidfuzz |
| AI | Groq `gpt-oss-120b`, with Amazon Bedrock (Nova) as fallback; structured outputs with evidence validation |
| Infrastructure | AWS CDK (Python), in the Mumbai region (`ap-south-1`) |

### AWS services

| Service | What it does here |
|---|---|
| Amazon CloudFront + Amazon S3 | Website hosting, and one HTTPS domain for both the site and the API |
| Amazon ECS on Fargate + Application Load Balancer | Runs the API, and the scheduled pipeline from the same container image |
| Amazon RDS for PostgreSQL (PostGIS) | Geospatial data, in isolated subnets |
| Amazon EventBridge | Runs the pipeline twice a day |
| AWS Secrets Manager | API keys, the session signing key, database credentials |
| Amazon Bedrock | AI fallback for classification |
| Amazon Location Service | Geocoding for place names the gazetteer can't resolve |
| AWS Certificate Manager | HTTPS for the custom domain |
| Amazon ECR | Container images |
| Amazon Polly | Narration for the demo video |

## Run locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
docker compose up -d db                      # PostGIS on port 5433
cd backend && uv sync
uv run python -m app.cli.seed_geo            # districts, talukas, gazetteer (one time)
uv run python -m app.cli.seed_crm            # demo government office, vendors, NGO and accounts
uv run python -m app.cli.run_pipeline        # collect, classify and zone once
uv run fastapi dev                           # API on :8000

cd ../frontend && npm install && npm run dev # app on :5173
```

Configuration goes in `backend/.env`. The keys used are `GROQ_API_KEY`, `APIFY_TOKEN`, `ADMIN_TOKEN`, `JWT_SECRET`, `DEMO_PASSWORD` and `AWS_PROFILE`.

## Tests

```bash
cd backend && uv run pytest -q                      # 360+ tests (PostGIS test database)
cd frontend && npx vitest run && npx tsc -b --noEmit
npm run build && npm run budgets                    # each route stays under 250 KB gzip
npx playwright test smoke a11y                      # end-to-end and accessibility
```

## Deploy

```bash
cd backend && uv run python ../infra/scripts/put_app_secret.py   # stores the keys in Secrets Manager
cd frontend && npm run build
cd infra && npx cdk deploy                                       # one stack; `npx cdk destroy` removes it
```

## Team

- **Sujal Kumar Singh**: lead, intelligence pipeline, drought data, AWS infrastructure
- **Chetan Kumar S M**: frontend and UX
- **Taran Pal Singh**: relief CRM (tenders, briefs, community, plans) and the demo video
