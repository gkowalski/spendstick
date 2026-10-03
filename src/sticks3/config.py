import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    admin_key: str
    serial_port: str | None
    poll_seconds: int
    refresh_seconds: int


def load_config(require_key: bool = True) -> Config:
    load_dotenv()
    key = os.environ.get("ANTHROPIC_ADMIN_API_KEY", "").strip()
    if require_key:
        if not key:
            raise SystemExit("ANTHROPIC_ADMIN_API_KEY is not set; add it to .env")
    return Config(
        admin_key=key,
        serial_port=os.environ.get("SERIAL_PORT", "").strip() or None,
        poll_seconds=int(os.environ.get("POLL_SECONDS", "60") or 60),
        refresh_seconds=int(os.environ.get("REFRESH_SECONDS", "300") or 300),
    )
