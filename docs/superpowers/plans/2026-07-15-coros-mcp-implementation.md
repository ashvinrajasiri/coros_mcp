# COROS MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local Python MCP server that any MCP host can use to read COROS metrics/activities and create + schedule sport-agnostic workouts on the COROS calendar.

**Architecture:** Thin stdio MCP (FastMCP) over a small Training Hub HTTP client. Agents own coaching; this server owns auth, payload mapping, and COROS I/O. v1 uses the **web** Training Hub API only (MD5 password → `accessToken`). Mobile-API sleep stages are deferred.

**Tech Stack:** Python 3.11+, `mcp` (FastMCP), `httpx`, `pydantic` v2, `pytest`, `python-dotenv` (optional local `.env` load).

**Spec:** `docs/superpowers/specs/2026-07-15-coros-mcp-design.md`

---

## File structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, `coros-mcp` console script |
| `.env.example` | Documented env vars (no secrets) |
| `src/coros_mcp/__init__.py` | Package version |
| `src/coros_mcp/errors.py` | `ToolError` + error codes → JSON shape |
| `src/coros_mcp/config.py` | Read/validate env (`COROS_EMAIL`, etc.) |
| `src/coros_mcp/models.py` | Pydantic I/O models for tools |
| `src/coros_mcp/sports.py` | Sport string ↔ COROS numeric `sportType` |
| `src/coros_mcp/auth.py` | Login, token cache, headers |
| `src/coros_mcp/client.py` | HTTP wrapper + endpoint methods |
| `src/coros_mcp/workouts.py` | Friendly steps ↔ COROS program steps |
| `src/coros_mcp/normalize.py` | Raw COROS JSON → agent-facing dicts |
| `src/coros_mcp/server.py` | FastMCP tool registration + entrypoint |
| `tests/test_*.py` | Unit tests (mapping, auth hashing, normalize, errors) |

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/coros_mcp/__init__.py`
- Create: `tests/conftest.py`
- Modify: `README.md`
- Modify: `.gitignore` (ensure `.venv/`, `.env`, token cache)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "coros-mcp"
version = "0.1.0"
description = "Sport-agnostic MCP server for COROS Training Hub"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "mcp>=1.6.0",
  "httpx>=0.28.0",
  "pydantic>=2.10.0",
  "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[project.scripts]
coros-mcp = "coros_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/coros_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `.env.example`**

```bash
COROS_EMAIL=you@example.com
COROS_PASSWORD=your-password
COROS_REGION=us
# Optional path to cache access token JSON
# COROS_TOKEN_CACHE=/tmp/coros_mcp_token.json
```

- [ ] **Step 3: Create package init + empty conftest**

```python
# src/coros_mcp/__init__.py
__version__ = "0.1.0"
```

```python
# tests/conftest.py
# Shared fixtures added in later tasks.
```

- [ ] **Step 4: Update README with purpose, env vars, watch-sync caveat, run command**

Include:
- Unofficial API warning
- Env vars table
- `pip install -e ".[dev]"` / `coros-mcp`
- Hermes / Claude Desktop MCP config JSON example (env in host config)
- Watch sync: MCP → COROS cloud → phone app → watch

- [ ] **Step 5: Create venv and install**

```bash
cd /Users/ashvinrajasiri/workspace/coros_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: install succeeds; `coros-mcp --help` may fail until server exists (OK).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example src/coros_mcp/__init__.py tests/conftest.py README.md .gitignore
git commit -m "chore: scaffold Python MCP package"
```

---

### Task 2: Errors and config

**Files:**
- Create: `src/coros_mcp/errors.py`
- Create: `src/coros_mcp/config.py`
- Create: `tests/test_errors.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_errors.py
from coros_mcp.errors import ToolError, error_payload

def test_error_payload_shape():
    err = ToolError("bad login", code="AUTH_FAILED", hint="Check credentials")
    assert error_payload(err) == {
        "error": "bad login",
        "code": "AUTH_FAILED",
        "hint": "Check credentials",
    }
```

```python
# tests/test_config.py
import pytest
from coros_mcp.config import load_config, ConfigError

def test_load_config_requires_email_password(monkeypatch):
    monkeypatch.delenv("COROS_EMAIL", raising=False)
    monkeypatch.delenv("COROS_PASSWORD", raising=False)
    with pytest.raises(ConfigError):
        load_config()

def test_load_config_defaults_region(monkeypatch):
    monkeypatch.setenv("COROS_EMAIL", "a@b.com")
    monkeypatch.setenv("COROS_PASSWORD", "secret")
    monkeypatch.delenv("COROS_REGION", raising=False)
    cfg = load_config()
    assert cfg.email == "a@b.com"
    assert cfg.password == "secret"
    assert cfg.region == "us"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
source .venv/bin/activate
pytest tests/test_errors.py tests/test_config.py -v
```

Expected: import/collection errors (modules missing).

- [ ] **Step 3: Implement**

```python
# src/coros_mcp/errors.py
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
```

```python
# src/coros_mcp/config.py
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
    return Config(email=email, password=password, region=region, token_cache=token_cache)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_errors.py tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/coros_mcp/errors.py src/coros_mcp/config.py tests/test_errors.py tests/test_config.py
git commit -m "feat: add config loading and tool error shape"
```

---

### Task 3: Sport map + workout step mapping (TDD core)

**Files:**
- Create: `src/coros_mcp/sports.py`
- Create: `src/coros_mcp/models.py`
- Create: `src/coros_mcp/workouts.py`
- Create: `tests/test_sports.py`
- Create: `tests/test_workouts.py`

COROS expects numeric `sportType` (e.g. run often `100`, bike `200` — verify against live Training Hub / community clients during implementation and adjust constants). Internally API durations are often **seconds**; distances often **centimeters**. Dates in API queries are `YYYYMMDD`.

- [ ] **Step 1: Write failing tests for sport resolve + simple run workout map**

```python
# tests/test_sports.py
from coros_mcp.sports import sport_to_type, type_to_sport

def test_run_sport_roundtrip():
    assert sport_to_type("run") == 100
    assert type_to_sport(100) == "run"

def test_unknown_sport_raises():
    import pytest
    from coros_mcp.errors import ToolError
    with pytest.raises(ToolError) as e:
        sport_to_type("quidditch")
    assert e.value.code == "VALIDATION_ERROR"
```

```python
# tests/test_workouts.py
from coros_mcp.workouts import friendly_to_coros_steps, coros_steps_to_friendly
from coros_mcp.models import WorkoutCreate

def test_simple_timed_interval_maps_duration_seconds():
    w = WorkoutCreate.model_validate({
        "name": "Easy",
        "sport": "run",
        "steps": [
            {"type": "warmup", "duration": {"unit": "time", "value": 10, "time_unit": "min"}},
            {"type": "steady", "duration": {"unit": "time", "value": 30, "time_unit": "min"}},
            {"type": "cooldown", "duration": {"unit": "time", "value": 5, "time_unit": "min"}},
        ],
    })
    steps = friendly_to_coros_steps(w.steps)
    assert isinstance(steps, list)
    assert len(steps) == 3
    # First step duration should be 600 seconds (exact key names may match COROS; assert via helper)
    assert steps[0]["duration"] == 600  # adjust key if COROS uses different field after discovery
```

> During implementation: when first live `create_workout` is attempted (Task 7), reconcile field names with a captured Training Hub payload. Keep unit tests asserting **our** intermediate COROS-shaped dict; update keys once confirmed. Do not invent undocumented fields without a recorded sample.

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_sports.py tests/test_workouts.py -v
```

- [ ] **Step 3: Implement `models.py` (tool I/O), `sports.py`, `workouts.py`**

Minimum models:

```python
# src/coros_mcp/models.py (sketch — expand as needed)
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class Duration(BaseModel):
    unit: Literal["time", "distance", "open"]
    value: float | None = None
    time_unit: Literal["sec", "min"] | None = "min"
    distance_unit: Literal["m", "km", "mi"] | None = "m"

class Target(BaseModel):
    kind: Literal["pace", "hr", "power", "cadence"]
    low: str | float | int
    high: str | float | int | None = None
    unit: str | None = None

class WorkoutStep(BaseModel):
    type: str
    duration: Duration | None = None
    target: Target | None = None
    count: int | None = None  # for repeat
    steps: list["WorkoutStep"] | None = None

class WorkoutCreate(BaseModel):
    name: str
    sport: str
    steps: list[WorkoutStep] = Field(default_factory=list)
```

`sports.py`: dict map for known sports; unknown → `ToolError(VALIDATION_ERROR)` for v1 (pass-through of raw int later if needed).

`workouts.py`:
- Convert time → seconds, distance → centimeters
- Pace strings `"4:30"` → COROS pace units (seconds per km is common; confirm live)
- Expand `repeat` into COROS nest structure
- Raise `ToolError(UNSUPPORTED_SPORT_STEP)` when a target/step cannot be represented

- [ ] **Step 4: Run — expect PASS** (update assertions once COROS field names locked)

```bash
pytest tests/test_sports.py tests/test_workouts.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/coros_mcp/models.py src/coros_mcp/sports.py src/coros_mcp/workouts.py tests/test_sports.py tests/test_workouts.py
git commit -m "feat: add sport-agnostic workout step mapping"
```

---

### Task 4: Auth (MD5 login + token cache)

**Files:**
- Create: `src/coros_mcp/auth.py`
- Create: `tests/test_auth.py`

Known web login pattern (community):

- `POST {base}/account/login`
- Body: `{"account": email, "accountType": 2, "pwd": md5_hex(password)}`
- Success: `result == "0000"`, `data.accessToken`, often `data.userId`
- Subsequent headers: `accesstoken: <token>`, `content-type: application/json`
- Bases: `us` → `https://teamapi.coros.com`, `eu` → `https://teameuapi.coros.com`, `cn` → confirm during impl (common: `https://teamcnapi.coros.com` or similar — verify before shipping)

- [ ] **Step 1: Write unit tests (no network)**

```python
# tests/test_auth.py
from coros_mcp.auth import hash_password, base_url_for_region

def test_hash_password_md5_hex():
    # md5("password") = 5f4dcc3b5aa765d61d8327deb882cf99
    assert hash_password("password") == "5f4dcc3b5aa765d61d8327deb882cf99"

def test_base_url_us():
    assert base_url_for_region("us") == "https://teamapi.coros.com"
```

- [ ] **Step 2: Run — FAIL, then implement `auth.py`**

```python
# src/coros_mcp/auth.py (core pieces)
import hashlib
import json
from pathlib import Path
import httpx
from coros_mcp.config import Config
from coros_mcp.errors import ToolError

REGION_BASE = {
    "us": "https://teamapi.coros.com",
    "eu": "https://teameuapi.coros.com",
    "cn": "https://teamcnapi.coros.com",  # verify
}

def hash_password(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()

def base_url_for_region(region: str) -> str:
    try:
        return REGION_BASE[region]
    except KeyError as e:
        raise ToolError("Invalid region", code="VALIDATION_ERROR") from e

class AuthSession:
    def __init__(self, config: Config):
        self.config = config
        self.access_token: str | None = None
        self.user_id: str | int | None = None

    def headers(self) -> dict[str, str]:
        if not self.access_token:
            raise ToolError("Not authenticated", code="UNAUTHORIZED", hint="Login first")
        return {"accesstoken": self.access_token, "content-type": "application/json"}

    def login(self, client: httpx.Client) -> None:
        # try token cache file if configured; else POST login; save cache; never log password
        ...
```

Also implement: load/save `COROS_TOKEN_CACHE` JSON `{"access_token", "user_id", "region"}`; on login failure raise `ToolError(AUTH_FAILED)`.

- [ ] **Step 3: pytest PASS for unit tests**

- [ ] **Step 4: Commit**

```bash
git add src/coros_mcp/auth.py tests/test_auth.py
git commit -m "feat: add COROS Training Hub auth and token cache"
```

---

### Task 5: HTTP client + normalize helpers

**Files:**
- Create: `src/coros_mcp/client.py`
- Create: `src/coros_mcp/normalize.py`
- Create: `tests/test_normalize.py`
- Create: `tests/test_client_response.py`

Endpoints (web API — names from community clients; confirm paths on first live use):

| Method | Path | Use |
|---|---|---|
| POST | `/account/login` | Auth |
| GET | `/analyse/dayDetail/query` | Daily metrics |
| GET | `/activity/query` | Activities list |
| GET | `/activity/detail/query` (or equivalent) | Activity detail — confirm |
| GET/POST | `/training/program/query` | List library |
| POST | `/training/program/create` or `/training/program/save` | Create library — confirm |
| POST | `/training/program/delete` | Delete library — confirm |
| GET | `/training/schedule/query` | Calendar |
| POST | `/training/schedule/update` | Schedule / unschedule |

Client rules:
- Parse JSON; if `result != "0000"` → `ToolError(COROS_API_ERROR)` with message
- On HTTP 401 or auth-like result: clear token, re-login once, retry (read and idempotent gets only by default; for writes, only retry on auth errors)
- Dates: accept ISO `YYYY-MM-DD` from tools; convert to `YYYYMMDD` for API

- [ ] **Step 1: Write normalize tests with fixture JSON snippets**

```python
# tests/test_normalize.py
from coros_mcp.normalize import normalize_activity_list_item

def test_normalize_activity_basic():
    raw = {
        "labelId": "abc",
        "name": "Morning Run",
        "sportType": 100,
        "totalTime": 3600,
        "distance": 10000.0,  # confirm unit from samples (m vs cm)
        "avgHr": 140,
        "trainingLoad": 80,
        "startTime": 1710000000,
    }
    out = normalize_activity_list_item(raw)
    assert out["sport"] == "run"
    assert out["title"] == "Morning Run"
    assert out["duration_sec"] == 3600
```

Use committed fixture files under `tests/fixtures/` once a real anonymized response is captured.

- [ ] **Step 2: Implement `normalize.py` + `client.py` methods**

`CorosClient` methods (signatures):

```python
class CorosClient:
    def ensure_auth(self) -> None: ...
    def get_day_detail(self, start: str, end: str) -> dict: ...
    def query_activities(self, start: str, end: str, page: int = 1, size: int = 50) -> dict: ...
    def get_activity(self, activity_id: str) -> dict: ...
    def list_programs(self) -> list[dict]: ...
    def get_program(self, program_id: str) -> dict: ...
    def create_program(self, payload: dict) -> dict: ...
    def delete_program(self, program_id: str) -> None: ...
    def query_schedule(self, start: str, end: str) -> dict: ...
    def update_schedule(self, payload: dict) -> dict: ...
```

- [ ] **Step 3: Unit-test `_check_response` / date helpers without network**

- [ ] **Step 4: Commit**

```bash
git add src/coros_mcp/client.py src/coros_mcp/normalize.py tests/test_normalize.py tests/test_client_response.py tests/fixtures
git commit -m "feat: add COROS HTTP client and response normalizers"
```

---

### Task 6: MCP tools — metrics + activities (read path)

**Files:**
- Create: `src/coros_mcp/server.py` (initial tools)
- Create: `tests/test_tool_metrics.py` (mock client)

- [ ] **Step 1: Implement FastMCP server with tools**

```python
# src/coros_mcp/server.py
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()  # optional local .env; hosts can still inject env
mcp = FastMCP("coros_mcp")

@mcp.tool()
def get_daily_metrics(start_date: str, end_date: str | None = None) -> dict:
    """Read daily COROS metrics (HRV, RHR, load, fatigue, sleep-as-available) for a date or range (YYYY-MM-DD)."""
    ...

@mcp.tool()
def list_activities(start_date: str, end_date: str) -> dict:
    """List completed COROS activities in a date range (YYYY-MM-DD)."""
    ...

@mcp.tool()
def get_activity(activity_id: str) -> dict:
    """Get one completed activity by id."""
    ...

def main() -> None:
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

Wrap all tool bodies:

```python
try:
    ...
except ToolError as e:
    return error_payload(e)
except ConfigError as e:
    return error_payload(ToolError(str(e), code="AUTH_FAILED", hint="Set COROS_EMAIL/PASSWORD in MCP host env"))
```

- [ ] **Step 2: Mock-based unit test that tool returns normalized dict**

- [ ] **Step 3: Manual smoke (optional, with real creds)**

```bash
export COROS_EMAIL=...
export COROS_PASSWORD=...
export COROS_REGION=us
# Use MCP inspector or a tiny script calling CorosClient.get_day_detail
```

- [ ] **Step 4: Commit**

```bash
git add src/coros_mcp/server.py tests/test_tool_metrics.py
git commit -m "feat: add read tools for metrics and activities"
```

---

### Task 7: MCP tools — library create/list/get/delete

**Files:**
- Modify: `src/coros_mcp/server.py`
- Modify: `src/coros_mcp/client.py` / `workouts.py` as needed after live payload capture
- Create: `tests/test_tool_library.py`

- [ ] **Step 1: Add tools**

```python
@mcp.tool()
def list_workouts(sport: str | None = None, name_contains: str | None = None) -> dict: ...

@mcp.tool()
def get_workout(workout_id: str) -> dict: ...

@mcp.tool()
def create_workout(name: str, sport: str, steps: list[dict]) -> dict:
    """Create a library workout from sport-agnostic steps. Agent owns coaching logic."""
    ...

@mcp.tool()
def delete_workout(workout_id: str) -> dict:
    """Delete one library workout by id."""
    ...
```

`create_workout` flow:
1. Validate with `WorkoutCreate`
2. `friendly_to_coros_steps`
3. Build program payload (`name`, `sportType`, steps, …)
4. `client.create_program`
5. Return `{id, name, sport}`

- [ ] **Step 2: Live discovery checkpoint (required once)**

With real account, use browser Network tab on `t.coros.com` while saving a simple run workout **or** inspect a community client’s create payload. Save an **anonymized** fixture to `tests/fixtures/create_program_request.json` and align `workouts.py` + `client.create_program`.

- [ ] **Step 3: Unit tests for validation errors + mapping integration**

- [ ] **Step 4: Commit**

```bash
git add src/coros_mcp tests/test_tool_library.py tests/fixtures
git commit -m "feat: add library workout tools"
```

---

### Task 8: MCP tools — calendar schedule / list / unschedule

**Files:**
- Modify: `src/coros_mcp/server.py`
- Modify: `src/coros_mcp/client.py`
- Create: `tests/test_tool_calendar.py`
- Create: `tests/fixtures/` schedule samples

Taxonomy (must honor):
- Library workout id ≠ scheduled entry ids (`plan_id`, `id_in_plan`, `happen_day`)
- `schedule_workout(workout_id, date)` attaches library workout onto calendar via `/training/schedule/update`
- `unschedule_workout(schedule_id)` uses schedule identifiers, not library id
- Multi-month ranges allowed; if response huge, return `truncated: true`

- [ ] **Step 1: Implement tools**

```python
@mcp.tool()
def list_scheduled_workouts(start_date: str, end_date: str) -> dict: ...

@mcp.tool()
def schedule_workout(workout_id: str, date: str) -> dict:
    """Schedule a library workout on YYYY-MM-DD (supports far-future dates). Syncs to watch via COROS app."""
    ...

@mcp.tool()
def unschedule_workout(schedule_id: str) -> dict:
    """Remove one scheduled calendar entry by schedule id from list_scheduled_workouts."""
    ...
```

- [ ] **Step 2: Live discovery for schedule update payload shape** (create + delete one test day entry manually via tools)

- [ ] **Step 3: Unit tests with fixtures for list parsing + id extraction**

- [ ] **Step 4: Commit**

```bash
git add src/coros_mcp tests/test_tool_calendar.py tests/fixtures
git commit -m "feat: add calendar schedule tools"
```

---

### Task 9: Host docs + end-to-end checklist

**Files:**
- Modify: `README.md`
- Create: `docs/hermes-mcp.example.json` (or equivalent snippet)

- [ ] **Step 1: Document Hermes config**

```json
{
  "mcpServers": {
    "coros": {
      "command": "/Users/ashvinrajasiri/workspace/coros_mcp/.venv/bin/coros-mcp",
      "args": [],
      "env": {
        "COROS_EMAIL": "you@example.com",
        "COROS_PASSWORD": "your-password",
        "COROS_REGION": "us"
      }
    }
  }
}
```

Adapt key names to whatever Hermes actually uses if different; note in README.

- [ ] **Step 2: E2E checklist in README**

1. `get_daily_metrics` for today  
2. `list_activities` last 14 days  
3. `create_workout` simple easy run  
4. `schedule_workout` for tomorrow  
5. Confirm in Training Hub calendar  
6. Open COROS phone app → sync → watch shows workout  

- [ ] **Step 3: Commit**

```bash
git add README.md docs/hermes-mcp.example.json
git commit -m "docs: add Hermes MCP config and E2E checklist"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run full unit suite**

```bash
source .venv/bin/activate
pytest -v
```

Expected: all unit tests PASS; live tests skipped without creds.

- [ ] **Step 2: Spec coverage check**

Confirm tools exist for every row in design “v1 tool surface”; env auth; sport-agnostic create; months-ahead schedule; structured errors; no secrets in git (`git status`, ensure `.env` untracked).

- [ ] **Step 3: Commit any fixups; push only if user asks**

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|---|---|
| Env auth portable across hosts | 1, 2, 9 |
| `get_daily_metrics` | 6 |
| `list_activities` / `get_activity` | 6 |
| Library CRUD (no update in v1 — create/list/get/delete) | 7 |
| Schedule / list / unschedule months ahead | 8 |
| Sport-agnostic steps; run/bike full, others best-effort | 3, 7 |
| Structured errors | 2, 6–8 |
| Watch sync documented | 1, 9 |
| Python MCP stdio | 1, 6 |
| Web API only v1 (no mobile sleep AES) | 4–6 (explicit non-goal) |

**Deferred vs design “sleep as available”:** use dayDetail fields when present; full REM/deep via mobile API is post-v1.

**No placeholders left:** live endpoint field names have explicit discovery checkpoints in Tasks 7–8 rather than TBD sections.
