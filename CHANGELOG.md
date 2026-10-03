# Changelog

Release notes for each tagged version, newest first. The host program and the dongle firmware share
a frame format, so **reflash the firmware and restart `uv run sticks3` on every upgrade** (see
"Updating to a new release" in the README).

## Unreleased

### Added
- **Reset screen**, a third screen in the rotation: countdown to the monthly reset (00:00 UTC on the
  first of the next month), month-to-date cost from the Cost API, and a month-elapsed progress bar.
  The reset time is computed locally; the Spend Limits API is Claude Enterprise only.
- New `reset` frame sent by the host, and `month_bounds` / `reset_frame` helpers with tests
  (including the December to January rollover).
- Screenshot of the running display in the README.

### Changed
- The BOOT button now cycles through all three screens.

### Upgrade notes
- Reflash the firmware and restart the host. An old host never sends the `reset` frame, so the new
  screen would stay on "waiting for host...".

## v0.2 - 2026-10-03

### Added
- Screen-switch countdown in the header, replacing the data-age timer. The red dot still marks data
  older than 3 minutes.
- README sections on creating an organization and credential for the Admin API, what the numbers
  cover, and a step-by-step firmware update procedure with a troubleshooting guide.

### Changed
- **Usage screen** is now a 7-day view: the headline is the 7-day token total, with 24 h in/out on
  the small line and a 7-bar daily chart. The host sends a new `spark7` series for it.
- **Cost screen** is now a 7-day view: the headline is the 7-day total, with today's cost below and
  the top model counted over the week instead of just today.
- Project named **spendstick** in the README.
- The host no longer rejects keys that don't start with `sk-ant-admin`. The API decides, and a
  401/403 now prints a hint (the Admin API needs an organization; individual accounts get
  `403 permission_error`).

### Fixed
- Corrected the README's description of the `hello` handshake check.

### Upgrade notes
- Reflash the firmware and restart the host. Until the host is restarted, the usage chart is empty.

## v0.1 - 2026-10-03

First release.

### Added
- Python host (`uv run sticks3`) that polls the Anthropic Admin API Usage and Cost reports every
  60 s and pushes compact JSON frames over USB serial. Options: `--once`, `--dry-run`, `--simulate`,
  `--port`. API key and serial port are configured in `.env`.
- PlatformIO firmware for the LilyGO T-Dongle C5 that alternates a Usage and a Cost screen every
  60 s on the 160x80 ST7735 LCD; the BOOT button flips screens manually.
- `hello` handshake so the host can identify the dongle (a StickS3 enumerates with the same
  VID:PID).
- Unit tests for the frame builders.

### Notes
- The USB-CDC port drops device output unless DTR is asserted; the host handles this.
- The LCD backlight is active-low on this board.
