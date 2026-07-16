from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    email: str
    password: str
    region: str = "us"
    token_cache: str | None = None
    # None = auto-detect from COROS account login `unit` field
    distance_unit: str | None = None


def load_config() -> Config:
    email = os.environ.get("COROS_EMAIL", "").strip()
    password = os.environ.get("COROS_PASSWORD", "")
    if not email or not password:
        raise ConfigError(
            "COROS_EMAIL and COROS_PASSWORD must be set in the MCP host environment"
        )
    region = os.environ.get("COROS_REGION", "us").strip().lower() or "us"
    if region not in {"us", "eu", "cn"}:
        raise ConfigError("COROS_REGION must be one of: us, eu, cn")
    token_cache = os.environ.get("COROS_TOKEN_CACHE") or None
    raw_unit = os.environ.get("COROS_DISTANCE_UNIT")
    distance_unit: str | None
    if raw_unit is None or not raw_unit.strip():
        distance_unit = None
    else:
        normalized = raw_unit.strip().lower()
        if normalized in {"mi", "mile", "miles", "imperial"}:
            distance_unit = "mi"
        elif normalized in {"km", "kilometer", "kilometers", "metric"}:
            distance_unit = "km"
        else:
            raise ConfigError("COROS_DISTANCE_UNIT must be km or mi")
    return Config(
        email=email,
        password=password,
        region=region,
        token_cache=token_cache,
        distance_unit=distance_unit,
    )
