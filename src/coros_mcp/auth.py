from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from coros_mcp.config import Config
from coros_mcp.errors import ToolError


_REGION_BASE_URLS = {
    "us": "https://teamapi.coros.com",
    "eu": "https://teameuapi.coros.com",
    "cn": "https://teamcnapi.coros.com",
}


def hash_password(password: str) -> str:
    """Return the MD5 hex digest required by the COROS login endpoint."""
    return hashlib.md5(password.encode("utf-8"), usedforsecurity=False).hexdigest()


def base_url_for_region(region: str) -> str:
    normalized_region = region.strip().lower()
    try:
        return _REGION_BASE_URLS[normalized_region]
    except KeyError as exc:
        raise ToolError(
            "COROS region must be one of: us, eu, cn",
            code="VALIDATION_ERROR",
            hint="Set COROS_REGION to us, eu, or cn.",
        ) from exc


class AuthSession:
    def __init__(self, config: Config):
        self._config = config
        self._access_token: str | None = None
        self.user_id: str | None = None
        self._load_token_cache()

    def headers(self) -> dict[str, str]:
        if not self._access_token:
            raise ToolError(
                "COROS access token is missing",
                code="UNAUTHORIZED",
                hint="Call login() before making authenticated requests.",
            )
        return {
            "accesstoken": self._access_token,
            "content-type": "application/json",
        }

    def login(self, client: httpx.Client) -> None:
        try:
            response = client.post(
                f"{base_url_for_region(self._config.region)}/account/login",
                json={
                    "account": self._config.email,
                    "accountType": 2,
                    "pwd": hash_password(self._config.password),
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ToolError(
                "COROS authentication failed",
                code="AUTH_FAILED",
                hint="Check your COROS email, password, and region.",
            ) from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        access_token = data.get("accessToken") if isinstance(data, dict) else None
        if payload.get("result") != "0000" or not isinstance(access_token, str) or not access_token:
            raise ToolError(
                "COROS authentication failed",
                code="AUTH_FAILED",
                hint="Check your COROS email, password, and region.",
            )

        self._access_token = access_token
        user_id = data.get("userId")
        self.user_id = str(user_id) if user_id is not None else None
        self._save_token_cache()

    def clear(self) -> None:
        self._access_token = None
        self.user_id = None
        cache_path = self._cache_path()
        if cache_path is not None:
            try:
                cache_path.unlink()
            except FileNotFoundError:
                pass

    def _cache_path(self) -> Path | None:
        return Path(self._config.token_cache) if self._config.token_cache else None

    def _load_token_cache(self) -> None:
        cache_path = self._cache_path()
        if cache_path is None:
            return

        try:
            payload: Any = json.loads(cache_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        access_token = payload.get("access_token") or payload.get("accessToken")
        if not isinstance(access_token, str) or not access_token:
            return

        cached_region = payload.get("region")
        if not isinstance(cached_region, str) or cached_region.strip().lower() != self._config.region:
            return

        self._access_token = access_token
        user_id = payload.get("user_id") or payload.get("userId")
        self.user_id = str(user_id) if user_id is not None else None

    def _save_token_cache(self) -> None:
        cache_path = self._cache_path()
        if cache_path is None or self._access_token is None:
            return

        payload: dict[str, str] = {
            "access_token": self._access_token,
            "region": self._config.region,
        }
        if self.user_id is not None:
            payload["user_id"] = self.user_id
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload))
