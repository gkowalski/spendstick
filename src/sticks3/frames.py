"""Pure functions turning Admin API buckets into the compact frames sent to the device."""

from collections import defaultdict
from datetime import datetime, timezone

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


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Start of the current UTC calendar month and the start of the next one (the reset)."""
    now = now.astimezone(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt


def reset_frame(now: datetime, mtd_buckets: list[dict], ts: int) -> dict:
    start, nxt = month_bounds(now)
    total = (nxt - start).total_seconds()
    left = max(0, int((nxt - now).total_seconds()))
    return {
        "t": "reset",
        "period": "monthly",
        "left_s": left,
        "date": nxt.strftime("%b %-d"),
        "elapsed": round(1 - left / total, 3),
        "mtd": round(sum(_bucket_cost(b) for b in mtd_buckets), 2),
        "ts": ts,
    }


def mtd_buckets(buckets: list[dict], now: datetime) -> list[dict]:
    """Keep only the buckets that start in the current UTC month (buckets without a start are kept)."""
    start, _ = month_bounds(now)
    out = []
    for b in buckets:
        st = b.get("starting_at")
        if st is None or datetime.fromisoformat(st.replace("Z", "+00:00")) >= start:
            out.append(b)
    return out


MODEL_ROWS = 4


def models_frame(daily_usage: list[dict], cost_buckets: list[dict], ts: int) -> dict:
    """Per-model 7-day tokens and cost, ranked by spend (then tokens). `n` is the total model count."""
    tokens: dict[str, int] = defaultdict(int)
    for b in daily_usage[-7:]:
        for r in b["results"]:
            tokens[r.get("model") or "other"] += sum(bucket_tokens(r).values())
    usd: dict[str, float] = defaultdict(float)
    for b in cost_buckets[-7:]:
        for r in b["results"]:
            usd[r.get("model") or "other"] += cents_to_usd(r["amount"])
    rows = [[m, tokens.get(m, 0), round(usd.get(m, 0.0), 2)] for m in set(tokens) | set(usd)]
    rows = [r for r in rows if r[1] > 0 or r[2] > 0]
    rows.sort(key=lambda r: (-r[2], -r[1], r[0]))
    return {"t": "models", "n": len(rows), "rows": rows[:MODEL_ROWS], "ts": ts}
