import argparse
import json
import time
from datetime import datetime, timezone

import httpx
import serial

from sticks3 import device
from sticks3.admin_api import AdminApi, RateLimited
from sticks3.config import load_config
from sticks3.frames import cost_frame, models_frame, mtd_buckets, reset_frame, usage_frame


def _sample_frames() -> list[dict]:
    ts = int(time.time())
    return [
        {
            "t": "usage",
            "h24": {"in": 412_000, "out": 168_000, "cache_r": 1_240_000, "cache_w": 96_000},
            "d7": {"in": 2_900_000, "out": 1_100_000, "cache_r": 8_400_000, "cache_w": 700_000},
            "spark24": [3, 5, 2, 0, 0, 0, 1, 4, 9, 14, 12, 8, 10, 15, 18, 11, 9, 7, 6, 12, 16, 10, 5, 3],
            "top": [["claude-opus-5", 1_200_000], ["claude-sonnet-5", 600_000]],
            "ts": ts,
        },
        {
            "t": "cost",
            "today": 4.82,
            "d7": 31.57,
            "spark7": [3.1, 5.2, 4.4, 6.0, 2.9, 5.1, 4.82],
            "top": [["claude-opus-5", 3.9], ["claude-sonnet-5", 0.9]],
            "ts": ts,
        },
        {
            "t": "models",
            "n": 5,
            "rows": [
                ["claude-opus-5", 1_200_000, 3.90],
                ["claude-sonnet-5", 600_000, 0.90],
                ["claude-sonnet-4-6", 96_401, 0.32],
                ["claude-haiku-4-5-20251001", 40_000, 0.02],
            ],
            "ts": ts,
        },
        reset_frame(datetime.now(timezone.utc), [{"results": [{"amount": "1840"}]}], ts),
    ]


STALE_AFTER_S = 900  # stop sending usage/cost if the API hasn't succeeded for this long (dot goes red)


def _fetch_raw(api: AdminApi) -> dict:
    return {"hourly": api.usage_24h(), "daily": api.usage_7d(), "cost": api.cost_window()}


def _build_frames(raw: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    ts = int(time.time())
    return [
        usage_frame(raw["hourly"], raw["daily"], ts),
        cost_frame(raw["cost"], ts),
        models_frame(raw["daily"], raw["cost"], ts),
        reset_frame(now, mtd_buckets(raw["cost"], now), ts),
    ]


def main() -> None:
    p = argparse.ArgumentParser(description="Push Anthropic usage/cost to a T-Dongle C5")
    p.add_argument("--once", action="store_true", help="fetch and send once, then exit")
    p.add_argument("--dry-run", action="store_true", help="print frames, don't touch the device")
    p.add_argument("--simulate", action="store_true", help="send canned data (no API key needed)")
    p.add_argument("--port", help="serial port (overrides SERIAL_PORT)")
    args = p.parse_args()

    cfg = load_config(require_key=not args.simulate)
    api = None if args.simulate else AdminApi(cfg.admin_key)
    port = args.port or cfg.serial_port
    ser: serial.Serial | None = None
    raw: dict | None = None
    raw_at = 0.0       # monotonic time of the last successful API refresh
    next_try = 0.0     # don't call the API before this monotonic time

    while True:
        frames: list[dict] = []
        try:
            if args.simulate:
                frames = _sample_frames()
            else:
                if time.monotonic() >= next_try and (
                    raw is None or time.monotonic() - raw_at >= cfg.refresh_seconds
                ):
                    next_try = time.monotonic() + cfg.refresh_seconds  # also the retry delay after errors
                    raw = _fetch_raw(api)
                    raw_at = time.monotonic()
                if raw is not None and time.monotonic() - raw_at <= STALE_AFTER_S:
                    frames = _build_frames(raw)
        except RateLimited as e:
            next_try = time.monotonic() + e.retry_after
            print(f"rate limited by the API; backing off {e.retry_after:.0f}s (showing cached data)")
            if raw is not None and time.monotonic() - raw_at <= STALE_AFTER_S:
                frames = _build_frames(raw)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            print(f"API error {code}: {e.response.text[:200]}")
            if code in (401, 403):
                print(
                    "hint: the key must be an Admin API key, an org:admin token, or a personal/service "
                    "key (not workspace-scoped) belonging to an organization; individual accounts "
                    "can't use the Admin API"
                )
            if raw is not None and time.monotonic() - raw_at <= STALE_AFTER_S:
                frames = _build_frames(raw)
        except httpx.HTTPError as e:
            print(f"network error: {e}")
            if raw is not None and time.monotonic() - raw_at <= STALE_AFTER_S:
                frames = _build_frames(raw)

        for f in frames:
            if args.dry_run:
                print(json.dumps(f))
                continue
            if ser is None:
                ser = device.find_device(port)
                if ser is None:
                    print("T-Dongle C5 not found; will retry")
                    break
                print(f"connected: {ser.port}")
            try:
                device.send(ser, f)
            except (serial.SerialException, OSError):
                print("device lost; will reconnect")
                ser.close()
                ser = None
                break

        if args.once:
            return
        time.sleep(cfg.poll_seconds)
