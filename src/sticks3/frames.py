"""Pure functions turning Admin API buckets into the compact frames sent to the device."""

from collections import defaultdict

TOP_N = 3


def bucket_tokens(result: dict) -> dict[str, int]:
    cc = result.get("cache_creation") or {}
    return {
        "in": result.get("uncached_input_tokens", 0),
        "out": result.get("output_tokens", 0),
        "cache_r": result.get("cache_read_input_tokens", 0),
        "cache_w": cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0),
    }


def _sum_tokens(buckets: list[dict]) -> dict[str, int]:
    total = {"in": 0, "out": 0, "cache_r": 0, "cache_w": 0}
    for b in buckets:
        for r in b["results"]:
            for k, v in bucket_tokens(r).items():
                total[k] += v
    return total


def _bucket_total(bucket: dict) -> int:
    return sum(sum(bucket_tokens(r).values()) for r in bucket["results"])


def _top_models(buckets: list[dict]) -> list[list]:
    per_model: dict[str, int] = defaultdict(int)
    for b in buckets:
        for r in b["results"]:
            per_model[r.get("model") or "unknown"] += sum(bucket_tokens(r).values())
    ranked = sorted(per_model.items(), key=lambda kv: kv[1], reverse=True)
    return [[m, n] for m, n in ranked[:TOP_N] if n > 0]


def usage_frame(hourly: list[dict], daily: list[dict], ts: int) -> dict:
    hourly = hourly[-24:]
    return {
        "t": "usage",
        "h24": _sum_tokens(hourly),
        "d7": _sum_tokens(daily),
        "spark24": [_bucket_total(b) for b in hourly],
        "spark7": [_bucket_total(b) for b in daily[-7:]],
        "top": _top_models(hourly),
        "ts": ts,
    }


def cents_to_usd(amount: str) -> float:
    return float(amount) / 100.0


def _bucket_cost(bucket: dict) -> float:
    return sum(cents_to_usd(r["amount"]) for r in bucket["results"])


def cost_frame(daily: list[dict], ts: int) -> dict:
    daily = daily[-7:]
    per_model: dict[str, float] = defaultdict(float)
    for b in daily:
        for r in b["results"]:
            per_model[r.get("model") or r.get("description") or "other"] += cents_to_usd(r["amount"])
    top = sorted(per_model.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    return {
        "t": "cost",
        "today": round(_bucket_cost(daily[-1]), 2) if daily else 0.0,
        "d7": round(sum(_bucket_cost(b) for b in daily), 2),
        "spark7": [round(_bucket_cost(b), 2) for b in daily],
        "top": [[m, round(c, 2)] for m, c in top if c > 0],
        "ts": ts,
    }
