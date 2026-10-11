"""One place for deploy settings. PROJECT names every AWS resource; the product name itself lives in the app config."""
PROJECT = "jal"
ACCOUNT = "328833518840"      # personal free-plan account (profile "spice"); never the office account
REGION = "ap-south-1"         # Mumbai
APP_SECRET_NAME = f"{PROJECT}/app"   # GROQ_API_KEY, APIFY_TOKEN, ADMIN_TOKEN (created by scripts/put_app_secret.py)
PIPELINE_CRON_HOURS = "0,12"  # UTC: 05:30 and 17:30 IST; each run costs about $0.2 of Apify
# custom domain (optional): set both to "" to serve only the cloudfront.net address. The certificate must be in us-east-1.
DOMAIN_NAME = "jaljeevan.sujalsingh.dev"
CERTIFICATE_ARN = "arn:aws:acm:us-east-1:328833518840:certificate/f41cb82c-c793-4591-bfb2-f7069734fbb9"
