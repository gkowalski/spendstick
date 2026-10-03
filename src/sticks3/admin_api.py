import time
from datetime import datetime, timedelta, timezone

import httpx

BASE = "https://api.anthropic.com/v1/organizations"


class AdminApi:
    def __init__(self, key: str, client: httpx.Client | None = None):
        self._client = client or httpx.Client(timeout=20)
        self._headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}

    def _get_all(self, path: str, params: dict) -> list[dict]:
        buckets: list[dict] = []
        params = dict(params)
        while True:
            data = self._get(path, params)
            buckets.extend(data["data"])
            if not data.get("has_more") or not data.get("next_page"):
                return buckets
            params["page"] = data["next_page"]

    def _get(self, path: str, params: dict) -> dict:
        for attempt in range(4):
            resp = self._client.get(f"{BASE}/{path}", params=params, headers=self._headers)
            if resp.status_code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable")

    def usage_24h(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        return self._get_all(
            "usage_report/messages",
            {
                "starting_at": _iso(now - timedelta(hours=24)),
                "ending_at": _iso(now + timedelta(hours=1)),
                "bucket_width": "1h",
                "group_by[]": "model",
                "limit": 48,
            },
        )

    def usage_7d(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        return self._get_all(
            "usage_report/messages",
            {
                "starting_at": _iso(now - timedelta(days=6)),
                "ending_at": _iso(now + timedelta(days=1)),
                "bucket_width": "1d",
                "group_by[]": "model",
                "limit": 8,
            },
        )

    def cost_7d(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        return self._get_all(
            "cost_report",
            {
                "starting_at": _iso(now - timedelta(days=6)),
                "ending_at": _iso(now + timedelta(days=1)),
                "bucket_width": "1d",
                "group_by[]": "description",
                "limit": 8,
            },
        )


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
