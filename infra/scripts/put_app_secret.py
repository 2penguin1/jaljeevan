"""Create or update the app secret in Secrets Manager from backend/.env, without ever printing a value.

  cd infra && uv run python scripts/put_app_secret.py

Keys: GROQ_API_KEY, APIFY_TOKEN, ADMIN_TOKEN (ADMIN_TOKEN is generated and saved to backend/.env if missing).
"""
import json
import secrets
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import APP_SECRET_NAME, REGION  # noqa: E402

ENV = Path(__file__).resolve().parents[2] / "backend" / ".env"
KEYS = ("GROQ_API_KEY", "APIFY_TOKEN", "ADMIN_TOKEN")


def read_env(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def main() -> None:
    env = read_env(ENV)
    if not env.get("ADMIN_TOKEN"):
        env["ADMIN_TOKEN"] = secrets.token_urlsafe(32)
        with ENV.open("a", encoding="utf-8") as fh:
            fh.write(f"\nADMIN_TOKEN={env['ADMIN_TOKEN']}\n")
        print("generated ADMIN_TOKEN and saved it to backend/.env")
    missing = [k for k in KEYS if not env.get(k)]
    if missing:
        sys.exit(f"missing in backend/.env: {', '.join(missing)}")
    value = json.dumps({k: env[k] for k in KEYS})
    client = boto3.Session(profile_name="spice", region_name=REGION).client("secretsmanager")
    try:
        client.create_secret(Name=APP_SECRET_NAME, SecretString=value,
                             Description="App keys for the water-crisis platform (Groq, Apify, admin token)")
        print(f"created secret {APP_SECRET_NAME} with keys: {', '.join(KEYS)}")
    except client.exceptions.ResourceExistsException:
        client.put_secret_value(SecretId=APP_SECRET_NAME, SecretString=value)
        print(f"updated secret {APP_SECRET_NAME} with keys: {', '.join(KEYS)}")


if __name__ == "__main__":
    main()
