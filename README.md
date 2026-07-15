# coros-mcp

Sport-agnostic [Model Context Protocol](https://modelcontextprotocol.io/) server for the COROS Training Hub. Lets any MCP-capable AI agent (Hermes, Claude Desktop, ChatGPT with local MCP, etc.) read training data, manage workout library entries, and schedule workouts on the COROS calendar.

Coaching logic (goals, periodization, workout selection) lives in the **agent**, not in this server.

## Unofficial API warning

COROS does not publish a public developer API. This server uses the same private HTTPS endpoints as [COROS Training Hub](https://t.coros.com). Those endpoints can change or break when COROS updates the web app. Use at your own risk.

## Watch sync

Changes flow in one direction:

```text
MCP → COROS cloud → COROS phone app → watch
```

The MCP writes to COROS cloud only. Your phone app must sync to push scheduled workouts to the watch. If the phone is offline, a newly scheduled workout may not appear on the watch until sync completes.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `COROS_EMAIL` | Yes | — | COROS account email |
| `COROS_PASSWORD` | Yes | — | COROS account password |
| `COROS_REGION` | No | `us` | API region: `us`, `eu`, or `cn` |
| `COROS_TOKEN_CACHE` | No | — | Path to cache session token JSON across restarts |

Copy `.env.example` to `.env` for local development. **MCP hosts do not read project `.env` automatically** — each host must pass these variables when it starts the server (see config examples below).

## Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
coros-mcp
```

The `coros-mcp` console script starts the MCP server over stdio. Run tests with `pytest`.

## MCP host configuration

Pass credentials in the host config, not in the repo.

### Hermes / Claude Desktop

```json
{
  "mcpServers": {
    "coros": {
      "command": "/path/to/coros_mcp/.venv/bin/coros-mcp",
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

Adapt the config key names to your host if they differ (e.g. `mcp_servers` vs `mcpServers`).

## Design

See `docs/superpowers/specs/2026-07-15-coros-mcp-design.md` for architecture, tool surface, and data models.
