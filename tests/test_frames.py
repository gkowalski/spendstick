from sticks3.frames import cents_to_usd, cost_frame, usage_frame


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
    assert f["top"] == [["a", 1.0], ["b", 0.5]]


def test_cost_frame_empty():
    assert cost_frame([], ts=1)["today"] == 0.0
