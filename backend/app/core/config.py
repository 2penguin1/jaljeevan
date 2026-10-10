from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, read from environment variables / backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Jal (working name)"
    database_url: str = "postgresql+psycopg://jal:jal@localhost:5433/jal"
    aws_region: str = "ap-south-1"
    aws_profile: str | None = None  # "spice" (personal account); NEVER the office "default" profile
    classify_model: str = "in.anthropic.claude-haiku-4-5-20251001-v1:0"  # Haiku 5.5 blocked on free plan
    brief_model: str = "in.anthropic.claude-haiku-4-5-20251001-v1:0"
    raw_bucket: str | None = None
    raw_dir: str = "data/raw"
    apify_token: str | None = None
    apify_reddit_actor: str = "harshmaur/reddit-scraper"  # paid per result; the free 'lite' actor was blocked
    reddit_enabled: bool = True
    apify_x_actor: str = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"  # no 10-item cap
    apify_max_usd_per_run: float = 0.5
    max_post_age_days: int = 30
    admin_token: str | None = None  # admin API stays locked until ADMIN_TOKEN is configured


settings = Settings()
