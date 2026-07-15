# COROS MCP Design

**Date:** 2026-07-15  
**Status:** Approved for implementation planning  
**Repo:** `coros_mcp`

## Goal

Build a local, sport-agnostic [Model Context Protocol](https://modelcontextprotocol.io/) server that any MCP-capable AI agent (Hermes on a Mac mini, Claude Desktop, ChatGPT with local MCP, etc.) can use to:

1. **Read** training-relevant data from COROS (daily metrics, completed activities)
2. **Create** structured workouts in the COROS library
3. **Schedule / unschedule** workouts on the COROS calendar (including months ahead)

Coaching logic (goals, periodization, “what should I do tomorrow?”) lives in the **agent**, not in this MCP.

Primary personal use case is running, but the tool surface and workout schema must not be run-only.

## Non-goals (v1)

- Official COROS partner API (none exists publicly; we use Training Hub endpoints)
- Bluetooth / direct watch communication
- Built-in coaching, periodization, or pace-zone calculators
- Bulk destructive operations
- Equal, perfect step mapping for every COROS sport on day one

## Constraints

- COROS does not publish a public developer API. Access goes through the same private HTTPS endpoints used by [COROS Training Hub](https://t.coros.com). These can break when COROS changes the web app.
- The MCP writes to **COROS cloud**. The phone app syncs to the watch. If the phone is offline, the watch may not show a newly scheduled workout until sync occurs.
- Credentials must be portable across MCP hosts: supplied as environment variables by whoever launches the server, never hard-coded or committed.

## Architecture

```text
Any AI agent (Hermes / Claude / ChatGPT / …)
        │  MCP over stdio
        ▼
┌────────────────────────────────────┐
│  coros_mcp (Python)                │
│  • env-based auth                  │
│  • thin tool layer                 │
│  • sport-agnostic models           │
│  • map friendly JSON → COROS API   │
└────────────────┬───────────────────┘
                 │ unofficial Training Hub API
                 ▼
            COROS cloud
                 │ COROS app sync
                 ▼
            COROS watch
```

### Responsibilities

| Layer | Owns |
|---|---|
| Agent | Goals, plan length, workout selection, when to schedule |
| MCP | Auth, reads, create/delete library workouts, schedule/unschedule |
| COROS app / watch | Device sync and “Start” on the wrist |

### Why one thin MCP (not coaching inside the server)

- Works the same for Hermes, Claude, ChatGPT, or any future host
- Agents can implement different coaching styles without forking the MCP
- Smaller, testable surface area focused on COROS I/O

## Configuration

| Variable | Required | Description |
|---|---|---|
| `COROS_EMAIL` | Yes | COROS account email |
| `COROS_PASSWORD` | Yes | COROS account password |
| `COROS_REGION` | No | `us` (default), `eu`, or `cn` |
| `COROS_TOKEN_CACHE` | No | Path to cache session token across process lifetime / restarts |

Ship `.env.example` documenting these. Real secrets stay in the host MCP config (or a local gitignored `.env` for Hermes on the Mac mini).

**Portability note:** ChatGPT / Claude / Hermes do not read a random project `.env` automatically. Each host must pass env vars when it starts the MCP process. Same server binary; different host config.

## v1 tool surface

| Tool | Description |
|---|---|
| `get_daily_metrics` | Day (or short range) metrics: sleep, HRV, RHR, training load, fatigue as available |
| `list_activities` | Completed activities in a date range |
| `get_activity` | Detail for one activity by id |
| `list_workouts` | Library workouts (optional sport / name filter) |
| `get_workout` | Full library workout including steps |
| `create_workout` | Create a library workout from sport-agnostic JSON |
| `delete_workout` | Delete one library workout by id |
| `list_scheduled_workouts` | Calendar entries in a date range (supports multi-month windows) |
| `schedule_workout` | Schedule a library workout on a date (`YYYY-MM-DD`) |
| `unschedule_workout` | Remove one scheduled entry by schedule id |

Out of scope for v1 (candidates later): `move_scheduled_workout`, `replace_scheduled_workout`, strength exercise catalog search, FIT/GPX export, multi-delete.

## Data model

### Daily metrics

Normalized JSON fields the agent can reason over, e.g.:

- `date`
- `sleep` (duration / stages if available)
- `hrv`, `rhr`
- `training_load`, `fatigue`
- raw/passthrough extras under `raw` only when needed for debugging (keep default responses tidy)

### Activity

- `id`, `sport`, `start`, `duration_sec`, `distance_m`, `avg_hr`, `training_load`, `title`

### Library workout

- `id`, `name`, `sport`, `steps[]`

### Scheduled entry

- `schedule_id`, `date`, `workout_id`, `name`, `sport`

Scheduled entry ids are distinct from library workout ids.

### Sport-agnostic workout input

Agents call `create_workout` with friendly JSON. The MCP maps this to COROS’s internal representation.

```json
{
  "name": "Threshold 5x5min",
  "sport": "run",
  "steps": [
    {
      "type": "warmup",
      "duration": { "unit": "time", "value": 15, "time_unit": "min" }
    },
    {
      "type": "repeat",
      "count": 5,
      "steps": [
        {
          "type": "interval",
          "duration": { "unit": "time", "value": 5, "time_unit": "min" },
          "target": {
            "kind": "pace",
            "low": "4:30",
            "high": "4:40",
            "unit": "min_per_km"
          }
        },
        {
          "type": "recovery",
          "duration": { "unit": "time", "value": 2, "time_unit": "min" }
        }
      ]
    },
    {
      "type": "cooldown",
      "duration": { "unit": "time", "value": 10, "time_unit": "min" }
    }
  ]
}
```

**Rules**

- `sport` is a COROS sport key string (`run`, `bike`, `swim`, `strength`, …) — not a closed enum in the MCP public schema so new sports can be passed through
- Step `type`: `warmup` | `cooldown` | `interval` | `recovery` | `steady` | `repeat` | `rest` (extensible)
- Duration `unit`: `time` | `distance` | `open`
- Target `kind` (optional): `pace` | `hr` | `power` | `cadence`
- Nested `repeat` groups are allowed

**Sport support levels (v1)**

- **Full mapping:** run, bike (structured pace/power/HR steps)
- **Best-effort:** other sports — map what COROS accepts; return `UNSUPPORTED_SPORT_STEP` with a clear hint when a step/target cannot be represented

## Typical agent flows

### Flexible long plan

1. Agent asks user for goals / constraints (outside MCP)
2. Optionally `get_daily_metrics` + `list_activities` for context
3. For each planned session: `create_workout` → `schedule_workout(date)`
4. User opens COROS app so the watch syncs; morning “Start” uses today’s scheduled item

### Single day

1. Read recovery metrics
2. Create one workout
3. Schedule for tomorrow (or today)

### Cancel / reshape

1. `list_scheduled_workouts` for a range
2. `unschedule_workout` as needed
3. Create + schedule replacements

## Error handling

Tool failures return structured JSON:

```json
{
  "error": "human readable message",
  "code": "AUTH_FAILED",
  "hint": "Check COROS_EMAIL / COROS_PASSWORD / COROS_REGION in the MCP host config"
}
```

| Code | Meaning |
|---|---|
| `AUTH_FAILED` | Login rejected or region wrong |
| `UNAUTHORIZED` | Token expired and refresh failed |
| `NOT_FOUND` | Workout / activity / schedule id missing |
| `UNSUPPORTED_SPORT_STEP` | Step/target cannot be mapped for that sport |
| `VALIDATION_ERROR` | Bad agent input (dates, missing fields) |
| `COROS_API_ERROR` | Upstream non-success from Training Hub |
| `RATE_LIMITED` | Upstream throttling |

**Auth behavior:** login once per process; cache token; retry once on `401` after re-login. Never log or return the password.

**Safety:** `delete_workout` and `unschedule_workout` accept a single id only in v1.

**Large ranges:** multi-month `list_scheduled_workouts` / `list_activities` may paginate or return `truncated: true` with a hint to narrow the window.

## Project layout (planned)

```text
coros_mcp/
  README.md
  .env.example
  pyproject.toml
  src/coros_mcp/
    __init__.py
    server.py          # MCP tool registration
    auth.py            # login + token cache
    client.py          # Training Hub HTTP client
    models.py          # pydantic models for tool I/O
    workouts.py        # friendly steps ↔ COROS payload
    tools/
      metrics.py
      activities.py
      library.py
      calendar.py
  tests/
    test_workouts_mapping.py
    ...
  docs/superpowers/specs/
    2026-07-15-coros-mcp-design.md
```

## Testing strategy

- **Unit tests:** workout JSON ↔ COROS payload mapping; date/range validation; error shaping
- **Integration tests (optional):** live calls gated on `COROS_EMAIL` / `COROS_PASSWORD`; skipped when unset
- No CI dependency on real COROS credentials

## Risks

| Risk | Mitigation |
|---|---|
| Unofficial API breaks | Isolate HTTP in `client.py`; keep mapping tests; document breakage symptom |
| Watch not updated | Document phone-sync requirement in README and tool descriptions |
| Host can’t pass env (some cloud MCP setups) | Document supported local hosts; MCP requires local process with secrets |
| Partial sport support | Explicit errors; expand mappings iteratively |

## Success criteria

1. From Hermes (or another MCP host) with env configured, an agent can read recent metrics/activities
2. An agent can create a structured run workout and schedule it on a future date months ahead
3. That scheduled workout appears in COROS Training Hub / app calendar and can sync to the watch
4. The same server starts under a different host by changing only MCP launch config (command + env)
5. No secrets committed to git

## Implementation notes

- Language: Python
- Transport: MCP stdio (standard for local agents)
- Prefer a maintained Python MCP SDK for tool registration
- Reference community Knowledge of Training Hub endpoints while implementing our own clean client (do not vendor another MCP’s tool UX wholesale)
