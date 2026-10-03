# spendstick

T-Dongle C5 Anthropic usage/cost display.

A Python program on the Mac polls Anthropic's Admin API (Messages Usage + Cost reports) every
60 s and pushes compact JSON over USB serial to a LilyGO T-Dongle C5, which alternates a Usage
screen and a Cost screen every 60 s on its 160x80 LCD.

## Getting an API key
The Usage and Cost reports come from Anthropic's **Admin API**, which is **unavailable for individual
accounts**. You need an organization:

1. In the Claude Console (platform.claude.com) create an organization: Settings -> Organization.
   You become its admin.
2. Create a credential. The Admin API accepts any of these:
   - an **Admin API key** (`sk-ant-admin...`, sent as `x-api-key`; only org admins can create one,
     Settings -> Admin keys, and it is shown once);
   - an OAuth bearer token with the `org:admin` scope;
   - a personal or service-account key that isn't scoped to a specific workspace.
3. Put it in `.env` as `ANTHROPIC_ADMIN_API_KEY`. A key from an individual account (no
   organization) fails with `403 permission_error: Missing permissions`.

What the numbers mean:
- Reports cover **API usage inside that organization only**: calls made with the organization's keys.
  Usage from a personal account or a Claude Code subscription is not included, and a new
  organization starts at zero.
- Cost is reported in **daily** buckets (UTC), so the cost screen shows today + a 7-day chart. Usage
  uses hourly buckets for the last 24 h plus a 7-day total. Charts can have fewer bars than their
  window (e.g. a young organization).
- Cost amounts come back in cents as decimal strings; the program converts them to dollars.

## Setup
1. `cp .env.example .env` and set `ANTHROPIC_ADMIN_API_KEY` (see above). `.env` is gitignored.
2. Optionally set `SERIAL_PORT` (e.g. `/dev/cu.usbmodem1134101`). Left empty, the program scans
   Espressif USB ports and picks the one that answers the `hello` handshake.
3. Check it: `uv run sticks3 --dry-run --once` should print a `usage` and a `cost` frame.
   `403` means the key lacks Admin API access; `401` means the key is wrong.

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
- The USB-CDC port drops device output unless DTR is asserted; `device.open_port` handles this.
- The StickS3 and the dongle share VID:PID 303A:1001, hence the handshake.
