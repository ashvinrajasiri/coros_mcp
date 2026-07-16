# coros-mcp

Local [MCP](https://modelcontextprotocol.io/) server for the unofficial COROS Training Hub API. Any MCP host (Hermes, Claude Desktop, etc.) can read training data, create library workouts, and schedule them on the COROS calendar.

Coaching stays in the agent. This server is thin I/O only.

## Unofficial API

COROS has no public developer API. This talks to the same private HTTPS endpoints as [Training Hub](https://training.coros.com). Endpoints can change without notice.

## How data reaches the watch

```text
Agent → coros-mcp → COROS cloud → phone app sync → watch
```

The MCP never talks to the watch over Bluetooth. After scheduling, sync the COROS phone app.

## Install

```bash
git clone https://github.com/ashvinrajasiri/coros_mcp.git
cd coros_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Updates on a machine that already has a clone:

```bash
cd /path/to/coros_mcp
git pull
source .venv/bin/activate
pip install -e .
# then reload MCP in the host (e.g. Hermes: /reload-mcp)
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `COROS_EMAIL` | Yes | — | COROS account email |
| `COROS_PASSWORD` | Yes | — | COROS account password |
| `COROS_REGION` | No | `us` | `us`, `eu`, or `cn` (Canada → `us`) |
| `COROS_DISTANCE_UNIT` | No | auto | Optional `km` or `mi`. If unset, uses your COROS account unit from login |
| `COROS_TOKEN_CACHE` | No | — | Path to cache the session token across restarts |

Copy `.env.example` → `.env` for local scripts. **MCP hosts do not load project `.env`** — put credentials in the host config `env` block (below).

## Hermes setup

On the machine where Hermes runs (e.g. Mac mini), install the package (see above), then add a server entry. Examples:

- YAML: [`docs/hermes-mcp.example.yaml`](docs/hermes-mcp.example.yaml)
- JSON: [`docs/hermes-mcp.example.json`](docs/hermes-mcp.example.json)

Point `command` at **this clone’s** `.venv/bin/coros-mcp`, and set `COROS_EMAIL` / `COROS_PASSWORD` / `COROS_REGION` in `env`.

After `git pull`, run `pip install -e .` again if dependencies changed, then `/reload-mcp` in Hermes.

## Creating workouts with pace

Agents should send human paces, not raw COROS integers:

```json
{
  "name": "Easy 45min",
  "sport": "run",
  "steps": [
    {
      "type": "warmup",
      "duration": { "unit": "time", "value": 10, "time_unit": "min" },
      "target": { "kind": "pace", "low": "5:45", "high": "6:10", "unit": "min_per_km" }
    },
    {
      "type": "steady",
      "duration": { "unit": "time", "value": 25, "time_unit": "min" },
      "target": { "kind": "pace", "low": "5:45", "high": "6:10", "unit": "min_per_km" }
    },
    {
      "type": "cooldown",
      "duration": { "unit": "time", "value": 10, "time_unit": "min" },
      "target": { "kind": "pace", "low": "5:45", "high": "6:10", "unit": "min_per_km" }
    }
  ]
}
```

Also accepted: `"9:30/mi"`, `"5:45-6:10/km"`, or bare `"5:45"` (interpreted with the account’s unit).

### What COROS stores (for debugging)

| Field | Meaning |
|---|---|
| `intensityType` | `3` = pace |
| `intensityValue` / `intensityValueExtend` | **Seconds per kilometer** (e.g. `345` = 5:45/km) |
| `intensityDisplayUnit` | Hub dropdown only: `1` = min/km, `2` = min/mi |

Mile inputs are converted to seconds/km before upload. The dropdown unit follows your COROS account setting (override with `COROS_DISTANCE_UNIT`).

**Important:** Updating this MCP does not rewrite workouts already saved in COROS. Bad paces from older builds stay wrong until you recreate (and reschedule) those workouts.

## Tools

| Tool | Purpose |
|---|---|
| `get_daily_metrics` | Sleep / recovery-style daily metrics |
| `list_activities` / `get_activity` | Completed activities |
| `list_workouts` / `get_workout` / `create_workout` / `delete_workout` | Library |
| `list_scheduled_workouts` / `schedule_workout` / `unschedule_workout` | Calendar |

## Quick check

1. `get_daily_metrics` for today  
2. `create_workout` with a short easy run and pace targets  
3. Confirm paces in Training Hub (e.g. `5'45"–6'10" min/km`)  
4. `schedule_workout` → sync phone app → check watch  

## Design

See [`docs/superpowers/specs/2026-07-15-coros-mcp-design.md`](docs/superpowers/specs/2026-07-15-coros-mcp-design.md).

## Dev

```bash
pip install -e ".[dev]"
pytest
```
