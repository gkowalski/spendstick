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
Install PlatformIO once with `uv tool install platformio`. The first build downloads the ESP32-C5
toolchain and takes a few minutes; later builds take seconds.

### Updating to a new release
The host program and the firmware share a JSON frame format, so update both together.

1. **Stop the host:** press Ctrl-C in the terminal running `uv run sticks3`.
2. **Get the release:**
   ```
   git fetch --tags && git checkout <tag>        # e.g. v0.2, or `git pull` to follow main
   uv sync                                        # refresh Python deps
   ```
3. **Find the dongle's port:** `ls /dev/cu.usbmodem*`. The name can change when you replug it, and
   other Espressif boards (e.g. a StickS3) use the same pattern, so unplug the others if unsure.
4. **Flash it:**
   ```
   cd firmware
   pio run -t upload --upload-port /dev/cu.usbmodemXXXX
   cd ..
   ```
   Success ends with `Hash of data verified` and `[SUCCESS]`. The dongle reboots by itself.
5. **Restart the host:** `uv run sticks3`. The screen shows "waiting for host..." until the first frame
   arrives (up to a minute).

If you see a stale `VIRTUAL_ENV` warning from uv, open a fresh terminal or run `deactivate`.

### If the upload fails
- Make sure nothing else holds the port (the host program, a serial monitor).
- Enter download mode: unplug the dongle, hold the **BOOT** button, plug it back in, then release
  and run the upload again.

### Checking the firmware
`pio run -e diag` builds a minimal image that only prints `diag alive N` over serial, useful to
separate hardware problems from application bugs. To confirm the app is running, the handshake
returns its version:
```
uv run python -c "from sticks3 import device; s=device.open_port('/dev/cu.usbmodemXXXX'); print(device.handshake(s)); s.close()"
```
The BOOT button flips screens manually; the header shows seconds until the next switch, and its
dot turns red when data is over 3 minutes old.

## Notes
- The USB-CDC port drops device output unless DTR is asserted; `device.open_port` handles this.
- The StickS3 and the dongle share VID:PID 303A:1001, hence the handshake.
