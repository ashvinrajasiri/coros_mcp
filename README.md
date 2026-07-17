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

## Add to Claude, ChatGPT, or Hermes

Install the package on the **same computer** as the app (see [Install](#install)). Every host needs the absolute path to `.venv/bin/coros-mcp` plus your COROS credentials in `env`.

Replace `/path/to/coros_mcp` below with your clone path.

### Claude Desktop

1. Install coros-mcp (above).
2. Open **Claude Desktop → Settings → Developer → Edit Config** (or edit the file directly):
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
3. Merge this into the file (keep any other servers you already have):

```json
{
  "mcpServers": {
    "coros": {
      "command": "/path/to/coros_mcp/.venv/bin/coros-mcp",
      "args": [],
      "env": {
        "COROS_EMAIL": "you@example.com",
        "COROS_PASSWORD": "your-password",
        "COROS_REGION": "us",
        "COROS_TOKEN_CACHE": "/path/to/coros_mcp/.coros_token.json"
      }
    }
  }
}
```

4. Fully quit and reopen Claude Desktop.
5. Start a chat and ask something like “list my COROS workouts” — you should see `coros` tools available.

Same JSON shape: [`docs/hermes-mcp.example.json`](docs/hermes-mcp.example.json).

### ChatGPT desktop app

ChatGPT desktop (and Codex) support **local STDIO** MCP servers.

**UI (easiest):**

1. Install coros-mcp (above).
2. Open **Settings → MCP servers → Add server**.
3. Choose **STDIO**, name it `coros`.
4. Command: `/path/to/coros_mcp/.venv/bin/coros-mcp`
5. Add env vars: `COROS_EMAIL`, `COROS_PASSWORD`, `COROS_REGION` (and optional `COROS_TOKEN_CACHE`).
6. Save, then **Restart**.
7. In chat, type `/mcp` to confirm `coros` is connected.

**Or edit `~/.codex/config.toml`** (shared by ChatGPT desktop / Codex). Example: [`docs/chatgpt-codex.example.toml`](docs/chatgpt-codex.example.toml).

Notes:

- You need a ChatGPT plan/app build that exposes MCP servers (desktop; not the plain mobile web chat).
- This MCP is **local stdio only** — it is not a hosted URL you paste into ChatGPT web connectors/plugins.

### Hermes

On the machine where Hermes runs (e.g. Mac mini), add a server entry:

- YAML: [`docs/hermes-mcp.example.yaml`](docs/hermes-mcp.example.yaml)
- JSON: [`docs/hermes-mcp.example.json`](docs/hermes-mcp.example.json)

Point `command` at this clone’s `.venv/bin/coros-mcp`, set credentials in `env`, then `/reload-mcp`.

After any `git pull`, run `pip install -e .` again if needed, then reload MCP in the host.

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

## Strength workouts

Strength uses the live COROS exercise catalog (~380 moves), not free-text step names.

1. `search_strength_exercises("push")` → pick a catalog name  
2. `create_strength_workout` with reps or timed holds  
3. `schedule_workout` as usual  

```json
{
  "name": "Quick Push",
  "sets": 3,
  "exercises": [
    { "name": "Push Ups", "reps": 12, "rest_sec": 45 },
    { "name": "Planks", "duration_sec": 40, "rest_sec": 30 },
    { "name": "Squats", "reps": 15, "rest_sec": 45, "sets": 4 }
  ]
}
```

`sets` is consecutive sets **per exercise** (COROS stores it on each move). Workout-level `sets` is the default; an exercise can override with its own `sets`. Bodyweight for now (no weight targets yet).

## Tools

| Tool | Purpose |
|---|---|
| `get_daily_metrics` | Sleep / recovery-style daily metrics |
| `list_activities` / `get_activity` | Completed activities |
| `list_workouts` / `get_workout` / `create_workout` | Library (list/get return compact payloads) |
| `delete_workout` / `delete_workouts` | Delete one or many library workouts |
| `search_strength_exercises` / `create_strength_workout` | Strength catalog + create |
| `list_scheduled_workouts` / `schedule_workout` / `unschedule_workout` | Calendar |

## Token efficiency

Tool results are kept small so agent hosts (Hermes/OpenRouter) spend less per call:

- `list_workouts` → `{id, name, sport, step_count}` only  
- `get_workout` → compact steps; pass `raw=true` only when debugging  
- `search_strength_exercises` → `{id, name}` (default `limit=10`); `verbose=true` for metadata  
- `delete_workouts([…])` for bulk deletes instead of looping `delete_workout`  
- Prefer short date windows on calendar/activity list tools  
- For mass cleanup outside the agent, use `scripts/cleanup_workouts.py`

## Quick check

1. `get_daily_metrics` for today  
2. `create_workout` with a short easy run and pace targets  
3. Confirm paces in Training Hub (e.g. `5'45"–6'10" min/km`)  
4. `schedule_workout` → sync phone app → check watch  

## Bulk cleanup (no MCP tokens)

Deleting dozens of workouts through an agent burns context. Use the local script instead:

```bash
source .venv/bin/activate
# preview workouts with the old millisecond pace bug
python scripts/cleanup_workouts.py --bad-pace
# delete them (optional: also clear matching calendar entries)
python scripts/cleanup_workouts.py --bad-pace --unschedule --apply
```

## Dev

```bash
pip install -e ".[dev]"
pytest
```
