# AWS deploy (design + task list)

Approved in chat on 2026-10-11 (about 20:10 IST; the deadline is tonight). Account …8840, profile `spice`, region ap-south-1. This replaces the MVP spec's Lambda / Step Functions / SQS layout, because a single container is enough for the demo and fits the time left.

## Architecture

- **One CDK (Python) stack in `infra/`.** `cdk deploy` creates it and `cdk destroy` removes it. The project name is a single config value in `infra/config.py`.
- **Network:** a VPC across 2 AZs with public and isolated subnets and **no NAT gateway**.
  - The Fargate tasks run in the public subnets with a public IP, for outbound access to GDELT, Groq and Apify.
  - RDS sits in the isolated subnets. Its security group accepts traffic only from the task security group.
  - The ALB security group accepts traffic only from the CloudFront managed prefix list.
- **Database:** RDS PostgreSQL 16, db.t4g.micro, 20 GB gp3, single-AZ. Credentials are generated into Secrets Manager. PostGIS comes from the restored dump (`CREATE EXTENSION`).
- **API:** an ECS Fargate service (1 vCPU / 2 GB, 1 task) behind an ALB.
  - The image is built from `backend/Dockerfile`, with the WorldPop raster included and the GeoJSON seeds excluded.
  - The ALB health check is `/health`. The ALB idle timeout is 3600 s for SSE; the app sends a heartbeat every 15 s.
- **Website:** S3, private, behind CloudFront with origin access control.
  - A CloudFront Function rewrites paths without a file extension to `/index.html`, for SPA routes.
  - The `/api/*` behaviour goes to the ALB over HTTP, with caching disabled and all viewer headers except Host forwarded.
- **Pipeline:** an EventBridge schedule (twice a day) runs a Fargate task with `python -m app.cli.run_pipeline` from the same image.
- **Secrets:** Secrets Manager.
  - The generated RDS secret becomes the `DB_*` environment variables, and the app builds `DATABASE_URL` from them.
  - The app secret (`GROQ_API_KEY`, `APIFY_TOKEN`, `ADMIN_TOKEN`) is created from `backend/.env` by a script that never prints the values.
- **AWS permissions (task role):** `bedrock:InvokeModel*` (Nova Lite, and Claude for later), `geo-places:Geocode`, and read/write on the raw-archive S3 bucket (`RAW_BUCKET`).
- **Data:** the local `jal` database is copied with `pg_dump -Fc`, uploaded to S3, then loaded by a one-off Fargate task (`scripts/restore_db.py`, using `pg_restore --no-owner --no-acl`) inside the VPC.
- **Cost:** about $60–65 a month from the credits. After judging, run `cdk destroy`.

## Tasks

1. **Config:** the app builds `DATABASE_URL` from `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` when they are set (test).
2. **`backend/Dockerfile` + `.dockerignore`:** Python 3.13 slim, `uv sync --frozen --no-dev`, postgresql-client 16. Build it and check the API starts locally against the docker DB.
3. **`backend/scripts/restore_db.py`:** downloads the dump from S3 and runs `pg_restore` (test with a fake runner).
4. **`infra/` CDK app:** VPC, RDS, secrets, cluster, ALB service, scheduled task, buckets, CloudFront, website deployment. Check with `cdk synth`.
5. **Bootstrap and deploy:**
   - create the app secret, then `cdk deploy`;
   - dump, upload and run the restore task;
   - verify `/health`, `/api/v1/stats/overview`, the website and the map over the CloudFront URL.
6. **Docs:** add the deploy commands to CLAUDE.md, a simple-points entry to DECISIONS.md, and reminders (destroy after judging, rotate keys).
