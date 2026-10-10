from datetime import datetime, timezone

import httpx

from app.domain.entities import RawItem
from app.integrations.archive import LocalRawArchive, S3RawArchive, make_archive
from app.integrations.article import ArticleExtractor

ITEMS = [RawItem(source="rss", url="u", title="t", text="पानी नहीं",
                 published_at=datetime(2026, 10, 10, tzinfo=timezone.utc), meta={"q": 1})]


def test_local_archive_roundtrip(tmp_path):
    archive = LocalRawArchive(tmp_path)
    key = archive.save("rss", ITEMS, "run1")
    assert key.endswith("run1.jsonl") and archive.read(key) == ITEMS


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        class Body:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data
        return {"Body": Body(self.objects[(Bucket, Key)])}


def test_s3_archive_roundtrip():
    archive = S3RawArchive("raw-bucket", FakeS3())
    key = archive.save("rss", ITEMS, "run1")
    assert key.startswith("s3://raw-bucket/raw/rss/") and archive.read(key) == ITEMS


def test_factory_picks_local_without_bucket(tmp_path):
    assert isinstance(make_archive(bucket=None, local_dir=tmp_path, region="ap-south-1"), LocalRawArchive)


def test_article_extractor_replaces_short_text_with_body():
    html = "<html><body><article><h1>Tankers</h1>" + "<p>Residents of Barmer waited three days for water tankers while the panchayat said supply was disrupted.</p>" * 5 + "</article></body></html>"
    item = RawItem(source="gdelt", url="https://n.test/a", title="Tankers", text="Tankers", published_at=None)
    out = ArticleExtractor(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html)))).enrich([item])
    assert len(out[0].text) > 100 and "Barmer" in out[0].text and item.text == "Tankers"  # original untouched


def test_article_extractor_keeps_item_on_failure():
    def boom(_req):
        raise httpx.ConnectError("down")

    item = RawItem(source="gdelt", url="https://n.test/a", title="T", text="T", published_at=None)
    assert ArticleExtractor(httpx.Client(transport=httpx.MockTransport(boom))).enrich([item]) == [item]
