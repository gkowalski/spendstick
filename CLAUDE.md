# CLAUDE.md

Mac-side Python program + ESP32-C5 firmware that shows Anthropic Admin API usage/cost on a LilyGO T-Dongle C5 (160x80 ST7735 LCD). See README.md for setup and run commands.

## Layout
- `src/sticks3/` host program (package keeps the old `sticks3` name; console script `sticks3`)
  - `admin_api.py` Usage/Cost report calls (httpx, pagination, retry); `frames.py` pure API-buckets -> wire-frame functions (unit tested); `device.py` serial port discovery/handshake/send; `config.py` loads `.env`
- `firmware/` PlatformIO Arduino project (`src/main.cpp`); `diag/main.cpp` is a serial-only bring-up image (`pio run -e diag`)
- `tests/` pytest (`uv run pytest`)

## Wire protocol
Newline-delimited JSON host -> device over USB CDC: `{"t":"usage"|"cost"|"models"|"reset",...}` frames and `{"t":"hello"}` -> `{"ok":"tdongle-c5","fw":...}`. Keep `frames.py` and the parser in `firmware/src/main.cpp` in sync when changing fields.

## Gotchas
- Usage/Cost endpoints need an **Admin API key** (`sk-ant-admin...`, or a non-workspace-scoped personal/service key of an org member) in `.env` (gitignored). Never print or commit it.
- Cost report is daily buckets only and `amount` is a decimal string in **cents**.
- The device's USB-CDC drops output unless the host asserts **DTR**; keep RTS low so opening the port doesn't reset the chip (`device.open_port`).
- StickS3 and the dongle both enumerate as VID:PID 303A:1001; identify the dongle by the `hello` handshake or an explicit `SERIAL_PORT`. Don't assume `/dev/ttyUSB0` (macOS uses `/dev/cu.usbmodem*`).
- LCD backlight (GPIO 0) is active-low. Panel init (`INITR_MINI160x80` + `invertDisplay(true)`) works on the current unit.
- Needs `ARDUINO_USB_MODE=1` + `ARDUINO_USB_CDC_ON_BOOT=1` (build fails without the mode flag). Platform is pioarduino; board `esp32-c5-devkitc-1` reports 4MB but the chip has 16MB flash.
- Flashing overwrites the dongle's firmware: confirm with the user first. PlatformIO is installed via `uv tool install platformio`.
