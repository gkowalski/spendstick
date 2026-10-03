import json
import time

import serial
from serial.tools import list_ports

ESPRESSIF_VID = 0x303A


def open_port(path: str) -> serial.Serial:
    # The chip's USB-CDC drops its output unless DTR is asserted. RTS stays low (EN high) so
    # connecting doesn't reset it.
    ser = serial.Serial()
    ser.port = path
    ser.baudrate = 115200
    ser.timeout = 1
    ser.write_timeout = 2
    ser.dtr = True
    ser.rts = False
    ser.open()
    return ser


def handshake(ser: serial.Serial) -> bool:
    ser.reset_input_buffer()
    ser.write(b'{"t":"hello"}\n')
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        line = ser.readline().decode("utf-8", "ignore").strip()
        if line.startswith("{") and '"tdongle-c5"' in line:
            return True
    return False


def find_device(explicit: str | None = None) -> serial.Serial | None:
    """Return an open, handshaken connection, or None if the dongle isn't present."""
    if explicit:
        candidates = [explicit]
    else:
        candidates = [p.device for p in list_ports.comports() if p.vid == ESPRESSIF_VID]
    for path in candidates:
        try:
            ser = open_port(path)
        except (serial.SerialException, OSError):
            continue
        if explicit or handshake(ser):
            return ser
        ser.close()
    return None


def send(ser: serial.Serial, frame: dict) -> None:
    ser.write((json.dumps(frame, separators=(",", ":")) + "\n").encode())
    ser.flush()
