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
    distance_unit: str = "km"


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
    distance_unit = os.environ.get("COROS_DISTANCE_UNIT", "km").strip().lower() or "km"
    if distance_unit in {"mi", "mile", "miles", "imperial"}:
        distance_unit = "mi"
    elif distance_unit in {"km", "kilometer", "kilometers", "metric"}:
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
