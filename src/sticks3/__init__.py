import argparse
import json
import time

import httpx
import serial

from sticks3 import device
from sticks3.admin_api import AdminApi
from sticks3.config import load_config
from sticks3.frames import cost_frame, usage_frame


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
    ]


def _fetch_frames(api: AdminApi) -> list[dict]:
    ts = int(time.time())
    return [
        usage_frame(api.usage_24h(), api.usage_7d(), ts),
        cost_frame(api.cost_7d(), ts),
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

    while True:
        try:
            frames = _sample_frames() if args.simulate else _fetch_frames(api)
        except httpx.HTTPStatusError as e:
            print(f"API error {e.response.status_code}: {e.response.text[:200]}")
            frames = []
        except httpx.HTTPError as e:
            print(f"network error: {e}")
            frames = []

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
