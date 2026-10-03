import time
from datetime import datetime, timedelta, timezone

import httpx

BASE = "https://api.anthropic.com/v1/organizations"


class RateLimited(Exception):
    def __init__(self, retry_after: float):
        super().__init__(f"rate limited; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


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
        for attempt in range(3):
            resp = self._client.get(f"{BASE}/{path}", params=params, headers=self._headers)
            if resp.status_code == 429:
                # Don't sleep here: let the caller back off and keep serving cached data.
                raise RateLimited(_retry_after(resp))
            if resp.status_code in (500, 502, 503, 529) and attempt < 2:
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

    def cost_window(self, now: datetime | None = None) -> list[dict]:
        """Daily cost buckets covering both the last 7 days and the month to date (one call)."""
        now = now or datetime.now(timezone.utc)
        return self._get_all(
            "cost_report",
            {
                "starting_at": _iso(min(now - timedelta(days=6), _month_start(now))),
                "ending_at": _iso(now + timedelta(days=1)),
                "bucket_width": "1d",
                "group_by[]": "description",
                "limit": 31,
            },
        )


def _month_start(now: datetime) -> datetime:
    now = now.astimezone(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _retry_after(resp: httpx.Response) -> float:
    try:
        return min(max(float(resp.headers.get("retry-after", "60")), 1.0), 900.0)
    except ValueError:
        return 60.0


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
