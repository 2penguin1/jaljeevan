"""One-off: load a database dump (pg_dump -Fc) from S3 into the configured database.

Runs as an ECS task inside the VPC (the database is not reachable from the internet):
  python -m scripts.restore_db s3://<bucket>/<key>
The password goes to pg_restore through PGPASSWORD, never on the command line.
"""
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from app.core.config import Settings


def parse_s3(uri: str) -> tuple[str, str]:
    parts = urlsplit(uri)
    if parts.scheme != "s3" or not parts.netloc or not parts.path.strip("/"):
        raise ValueError(f"not an s3://bucket/key address: {uri}")
    return parts.netloc, parts.path.lstrip("/")


def restore(uri: str, s3=None, run=subprocess.run) -> int:
    settings = Settings(_env_file=None)
    bucket, key = parse_s3(uri)
    if s3 is None:
        import boto3
        s3 = boto3.client("s3", region_name=settings.aws_region)
    path = os.path.join(tempfile.gettempdir(), "restore.dump")
    s3.download_file(bucket, key, path)
    cmd = ["pg_restore", "--no-owner", "--no-acl", "--verbose", "-h", settings.db_host or "localhost",
           "-p", str(settings.db_port), "-U", settings.db_user or "postgres", "-d", settings.db_name, path]
    result = run(cmd, env={**os.environ, "PGPASSWORD": settings.db_password or ""}, capture_output=True, text=True)
    # pg_restore exits 1 on harmless warnings too (e.g. COMMENT ON EXTENSION needs the extension owner): show them
    errors = [ln for ln in (result.stderr or "").splitlines() if "error" in ln.lower()]
    print(f"pg_restore exit {result.returncode}; {len(errors)} error lines")
    for line in errors[:40]:
        print("  ", line)
    return result.returncode


if __name__ == "__main__":
    sys.exit(0 if restore(sys.argv[1]) in (0, 1) else 2)
