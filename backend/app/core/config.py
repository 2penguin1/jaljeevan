from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, read from environment variables / backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "JalJeevan"
    database_url: str = "postgresql+psycopg://jal:jal@localhost:5433/jal"
    aws_region: str = "ap-south-1"
    aws_profile: str | None = None  # "spice" (personal account); NEVER the office "default" profile
    classify_model: str = "in.anthropic.claude-haiku-4-5-20251001-v1:0"  # Haiku 5.5 blocked on free plan
    brief_model: str = "in.anthropic.claude-haiku-4-5-20251001-v1:0"
    llm_providers: str = "groq,nova,bedrock"  # fallback order; put bedrock first once a card is on the AWS account
    nova_model: str = "apac.amazon.nova-lite-v1:0"  # Amazon Nova on Bedrock: no Marketplace card needed
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    raw_bucket: str | None = None
    raw_dir: str = "data/raw"
    apify_token: str | None = None
    apify_reddit_actor: str = "harshmaur/reddit-scraper"  # paid per result; the free 'lite' actor was blocked
    reddit_enabled: bool = True
    apify_x_actor: str = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"  # no 10-item cap
    apify_max_usd_per_run: float = 0.5
    worldpop_path: str = "app/data/seed/ind_pop_2025_CN_1km_R2025A_UA_v1.tif"  # WorldPop 2025 1 km, CC BY 4.0
    chirps_base_url: str = "https://data.chc.ucsb.edu/products/SPI/CHIRPS3"
    gdo_soil_base_url: str = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/DROUGHTOBS/Drought_Observatories_datasets/"
                              "GDO_Soil_Moisture_Anomaly/ver3-0-1/")
    hf_token: str | None = None  # Hugging Face read token, for the gated IndicTrans2 model
    max_post_age_days: int = 30
    admin_token: str | None = None  # admin API stays locked until ADMIN_TOKEN is configured
    jwt_secret: str | None = None  # signs login sessions; required on servers (Secrets Manager)
    cookie_secure: bool = False  # true on AWS (HTTPS through CloudFront); false for http://localhost
    demo_password: str | None = None  # password of the seeded demo accounts (Secrets Manager / backend/.env)
    # on AWS the database password arrives as separate values from Secrets Manager; DATABASE_URL is built from them
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "jal"
    db_user: str | None = None
    db_password: str | None = None

    @model_validator(mode="after")
    def _database_url_from_parts(self) -> "Settings":
        if self.db_host and self.db_user and self.db_password:
            self.database_url = (f"postgresql+psycopg://{quote(self.db_user, safe='')}:{quote(self.db_password, safe='')}"
                                 f"@{self.db_host}:{self.db_port}/{self.db_name}")
        return self


settings = Settings()
