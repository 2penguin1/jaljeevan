from typing import Protocol

from app.core.exceptions import ExternalServiceError


class Locator(Protocol):
    def geocode(self, query: str) -> list[tuple[float, float]]: ...


class AmazonLocationClient:
    """Adapter over Amazon Location Service (geo-places v2: no resource to create, pay per request)."""

    def __init__(self, region: str, profile: str | None = None):
        import boto3

        self.client = boto3.Session(profile_name=profile, region_name=region).client("geo-places")

    def geocode(self, query: str) -> list[tuple[float, float]]:
        try:
            res = self.client.geocode(QueryText=query, Filter={"IncludeCountries": ["IND"]}, MaxResults=3)
        except Exception as exc:  # noqa: BLE001 - botocore raises many types; normalise them
            raise ExternalServiceError("amazon-location", type(exc).__name__) from None
        return [tuple(item["Position"]) for item in res.get("ResultItems", []) if item.get("Position")]
