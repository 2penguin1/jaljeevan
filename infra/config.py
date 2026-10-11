"""One place for deploy settings. PROJECT names every AWS resource; the product name itself lives in the app config."""
PROJECT = "jal"
ACCOUNT = "328833518840"      # personal free-plan account (profile "spice"); never the office account
REGION = "ap-south-1"         # Mumbai
APP_SECRET_NAME = f"{PROJECT}/app"   # GROQ_API_KEY, APIFY_TOKEN, ADMIN_TOKEN (created by scripts/put_app_secret.py)
PIPELINE_CRON_HOURS = "0,12"  # UTC: 05:30 and 17:30 IST; each run costs about $0.2 of Apify
