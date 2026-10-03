# spendstick

T-Dongle C5 Anthropic usage/cost display.

A Python program on the Mac polls Anthropic's Admin API (Messages Usage + Cost reports) every
60 s and pushes compact JSON over USB serial to a LilyGO T-Dongle C5, which alternates a Usage
screen and a Cost screen every 60 s on its 160x80 LCD.

## Setup
1. `cp .env.example .env` and set `ANTHROPIC_ADMIN_API_KEY` to an **Admin API key**
   (`sk-ant-admin...`, created in the Console by an org admin). Regular API keys can't read these reports.
2. Optionally set `SERIAL_PORT` (e.g. `/dev/cu.usbmodem1134101`). Left empty, the program scans
   Espressif USB ports and picks the one that answers the `hello` handshake.

## Run
```
uv run sticks3                 # poll + push forever
uv run sticks3 --once          # one fetch/push
uv run sticks3 --dry-run       # print frames, don't touch the device
uv run sticks3 --simulate      # canned data, no API key needed
uv run pytest                  # unit tests
```

## Firmware (`firmware/`, PlatformIO)
```
uv tool install platformio
cd firmware && pio run -t upload --upload-port <port>
```
`pio run -e diag` builds a minimal serial-only image for bring-up.
The BOOT button flips screens manually; the header dot turns red when data is over 3 min old.

## Notes
- Cost has daily buckets only, so the cost screen shows today (UTC) + a 7-day chart; usage shows the last 24 h (hourly) + 7-day total.
- The USB-CDC port drops device output unless DTR is asserted; `device.open_port` handles this.
- The StickS3 and the dongle share VID:PID 303A:1001, hence the handshake.
