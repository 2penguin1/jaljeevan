import httpx

from app.core.exceptions import ExternalServiceError


class ApifyClient:
    """Runs an Apify actor synchronously and returns its dataset items, with a hard spend cap per run."""

    BASE = "https://api.apify.com/v2/acts"

    def __init__(self, client: httpx.Client, token: str | None, max_usd_per_run: float):
        self.client = client
        self.token = token
        self.max_usd_per_run = max_usd_per_run

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def run_actor(self, actor_id: str, run_input: dict, max_items: int) -> list[dict]:
        if not self.configured:
            return []
        url = f"{self.BASE}/{actor_id.replace('/', '~')}/run-sync-get-dataset-items"
        params = {"token": self.token, "maxItems": max_items, "timeout": 240,
                  "maxTotalChargeUsd": self.max_usd_per_run}
        # Never put `exc` or the request URL in the message: the URL carries the API token.
        try:
            res = self.client.post(url, params=params, json=run_input, timeout=300)
        except httpx.HTTPError as exc:
            raise ExternalServiceError("apify", f"{actor_id} request failed ({type(exc).__name__})") from None
        if res.status_code >= 400:
            raise ExternalServiceError("apify", f"{actor_id} returned HTTP {res.status_code}",
                                       retryable=res.status_code >= 500 or res.status_code == 429)
        try:
            data = res.json()
        except ValueError:
            raise ExternalServiceError("apify", f"{actor_id} returned a non-JSON body") from None
        return data if isinstance(data, list) else []
