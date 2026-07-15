from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolError(Exception):
    message: str
    code: str
    hint: str = ""

    def __str__(self) -> str:
        return self.message


def error_payload(err: ToolError) -> dict[str, Any]:
    return {"error": err.message, "code": err.code, "hint": err.hint}
