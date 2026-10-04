from datetime import datetime, timezone

from sticks3.frames import cents_to_usd, cost_frame, models_frame, month_bounds, mtd_buckets, reset_frame, usage_frame


def _res(model, i=0, o=0, cr=0, c5=0, c1=0):
    return {
        "model": model,
        "uncached_input_tokens": i,
        "output_tokens": o,
        "cache_read_input_tokens": cr,
        "cache_creation": {"ephemeral_5m_input_tokens": c5, "ephemeral_1h_input_tokens": c1},
    }


def test_cents_to_usd():
    assert cents_to_usd("123.45") == 1.2345


def test_usage_frame_sums_and_top():
    hourly = [
        {"results": [_res("a", i=100, o=50), _res("b", i=10)]},
        {"results": []},
        {"results": [_res("a", cr=200, c5=5, c1=5)]},
    ]
    daily = [{"results": [_res("a", i=1000)]}]
    f = usage_frame(hourly, daily, ts=7)
    assert f["h24"] == {"in": 110, "out": 50, "cache_r": 200, "cache_w": 10}
    assert f["d7"]["in"] == 1000
    assert f["spark24"] == [160, 0, 210]
    assert f["spark7"] == [1000]
    assert f["top"] == [["a", 360], ["b", 10]]
    assert f["ts"] == 7


def test_cost_frame_cents_and_today():
    daily = [
        {"results": [{"amount": "250", "model": "a"}]},
        {"results": [{"amount": "100", "model": "a"}, {"amount": "50", "model": "b"}]},
    ]
    f = cost_frame(daily, ts=1)
    assert f["today"] == 1.5
    assert f["d7"] == 4.0
    assert f["spark7"] == [2.5, 1.5]
    assert f["top"] == [["a", 3.5], ["b", 0.5]]  # top models over the 7 days


def test_cost_frame_empty():
    assert cost_frame([], ts=1)["today"] == 0.0


def test_month_bounds_rolls_over_year():
    start, nxt = month_bounds(datetime(2026, 12, 15, 8, tzinfo=timezone.utc))
    assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert nxt == datetime(2027, 1, 1, tzinfo=timezone.utc)


def test_reset_frame_countdown_and_mtd():
    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    f = reset_frame(now, [{"results": [{"amount": "150"}]}, {"results": []}], ts=1)
    assert f["left_s"] == 36 * 3600  # 30 Oct 12:00 -> 1 Nov 00:00
    assert f["date"] == "Nov 1"
    assert f["mtd"] == 1.5
    assert 0.9 < f["elapsed"] < 1.0


def test_mtd_buckets_drops_previous_month():
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    buckets = [
        {"starting_at": "2026-09-30T00:00:00Z", "results": []},
        {"starting_at": "2026-10-01T00:00:00Z", "results": []},
        {"starting_at": "2026-10-02T00:00:00Z", "results": []},
    ]
    assert [b["starting_at"][:10] for b in mtd_buckets(buckets, now)] == ["2026-10-01", "2026-10-02"]


def test_models_frame_ranks_by_spend_and_caps_rows():
    daily = [{"results": [_res("a", i=100), _res("b", i=500), _res("c", i=1), _res("d", i=1), _res("e", i=1)]}]
    cost = [{"results": [{"amount": "300", "model": "a"}, {"amount": "100", "model": "b"}]}]
    f = models_frame(daily, cost, ts=1)
    assert f["n"] == 5
    assert [r[0] for r in f["rows"]] == ["a", "b", "c", "d"]  # ties broken by name
    assert f["rows"][0] == ["a", 100, 3.0]
    assert len(f["rows"]) == 4


def test_models_frame_empty():
    assert models_frame([], [], ts=1) == {"t": "models", "n": 0, "rows": [], "ts": 1}
