"""Raw-post archive (JSON Lines). Lets us re-classify after prompt/taxonomy changes without re-scraping."""
import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from app.domain.entities import RawItem
from app.integrations.dates import parse_dt
from app.integrations.ports import RawArchive


def _encode(item: RawItem) -> str:
    data = dataclasses.asdict(item)
    data["published_at"] = item.published_at.isoformat() if item.published_at else None
    return json.dumps(data, ensure_ascii=False)


def _decode(line: str) -> RawItem:
    data = json.loads(line)
    data["published_at"] = parse_dt(data["published_at"])
    return RawItem(**data)


def _relative_key(source: str, run_id: str) -> str:
    return f"raw/{source}/{datetime.now(timezone.utc):%Y-%m-%d}/{run_id}.jsonl"


class LocalRawArchive:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def save(self, source: str, items: list[RawItem], run_id: str) -> str:
        path = self.root / _relative_key(source, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(_encode(i) for i in items), encoding="utf-8")
        return str(path)

    def read(self, key: str) -> list[RawItem]:
        return [_decode(line) for line in Path(key).read_text(encoding="utf-8").splitlines() if line.strip()]


class S3RawArchive:
    def __init__(self, bucket: str, s3_client):
        self.bucket = bucket
        self.s3 = s3_client

    def save(self, source: str, items: list[RawItem], run_id: str) -> str:
        key = _relative_key(source, run_id)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body="\n".join(_encode(i) for i in items).encode("utf-8"))
        return f"s3://{self.bucket}/{key}"

    def read(self, key: str) -> list[RawItem]:
        bucket, _, path = key.removeprefix("s3://").partition("/")
        body = self.s3.get_object(Bucket=bucket, Key=path)["Body"].read().decode("utf-8")
        return [_decode(line) for line in body.splitlines() if line.strip()]


def make_archive(bucket: str | None, local_dir: Path | str, region: str, profile: str | None = None) -> RawArchive:
    """Factory: S3 when a bucket is configured (AWS), a local folder otherwise (laptop)."""
    if not bucket:
        return LocalRawArchive(local_dir)
    import boto3

    session = boto3.Session(profile_name=profile, region_name=region)
    return S3RawArchive(bucket, session.client("s3"))
