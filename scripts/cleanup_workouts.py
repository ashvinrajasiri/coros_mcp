#!/usr/bin/env python3
"""Bulk-delete COROS library workouts without burning MCP/agent tokens.

Uses local .env credentials. Dry-run by default; pass --apply to delete.

Examples:
  # Preview workouts with the old millisecond pace bug
  python scripts/cleanup_workouts.py --bad-pace

  # Delete them
  python scripts/cleanup_workouts.py --bad-pace --apply

  # Name filter (case-insensitive substring)
  python scripts/cleanup_workouts.py --name W1 --name Easy --apply

  # Also remove matching calendar entries in a date window
  python scripts/cleanup_workouts.py --bad-pace --unschedule --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from coros_mcp.client import CorosClient  # noqa: E402
from coros_mcp.errors import ToolError  # noqa: E402

# Absolute pace stored as seconds/km is typically 150–900.
# Old buggy builds wrote milliseconds (e.g. 345000).
_BAD_PACE_MIN_VALUE = 10_000
_DELETE_CHUNK = 25


def _pace_values(program: dict) -> list[int]:
    values: list[int] = []
    for exercise in program.get("exercises") or []:
        if not isinstance(exercise, dict):
            continue
        if exercise.get("intensityType") != 3:
            continue
        for key in ("intensityValue", "intensityValueExtend"):
            raw = exercise.get(key)
            if isinstance(raw, (int, float)) and raw > 0:
                values.append(int(raw))
    return values


def _is_bad_pace(program: dict) -> bool:
    values = _pace_values(program)
    return bool(values) and max(values) >= _BAD_PACE_MIN_VALUE


def _matches_name(name: str, needles: list[str]) -> bool:
    if not needles:
        return True
    lowered = name.lower()
    return all(needle.lower() in lowered for needle in needles)


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bad-pace",
        action="store_true",
        help="Select workouts whose pace intensity looks like old ms encoding",
    )
    parser.add_argument(
        "--name",
        action="append",
        default=[],
        help="Name must contain this substring (repeatable, AND logic)",
    )
    parser.add_argument(
        "--keep-name",
        action="append",
        default=[],
        help="Skip workouts whose name contains this substring",
    )
    parser.add_argument(
        "--unschedule",
        action="store_true",
        help="Also unschedule calendar entries with the same workout name",
    )
    parser.add_argument(
        "--schedule-days",
        type=int,
        default=400,
        help="Calendar window ahead to scan when --unschedule (default 400)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete/unschedule (otherwise dry-run)",
    )
    args = parser.parse_args()

    if not args.bad_pace and not args.name:
        parser.error("Provide --bad-pace and/or --name FILTER")

    client = CorosClient()
    client.ensure_auth()

    print("Listing library workouts…")
    programs = client.list_programs()
    selected: list[tuple[str, str, str]] = []
    for item in programs:
        wid = str(item.get("id") or "")
        name = str(item.get("name") or "")
        if not wid:
            continue
        if not _matches_name(name, args.name):
            continue
        if any(skip.lower() in name.lower() for skip in args.keep_name):
            continue
        if args.bad_pace:
            try:
                detail = client.get_program(wid)
            except ToolError as error:
                print(f"  skip {name!r}: {error}")
                continue
            if not _is_bad_pace(detail):
                continue
            reason = "bad-pace"
        else:
            reason = "name"
        selected.append((wid, name, reason))

    print(f"Matched {len(selected)} / {len(programs)} library workouts:")
    for wid, name, reason in selected[:50]:
        print(f"  [{reason}] {name} ({wid})")
    if len(selected) > 50:
        print(f"  … and {len(selected) - 50} more")

    schedule_ids: list[tuple[str, str, str]] = []
    if args.unschedule:
        start = date.today()
        end = start + timedelta(days=max(1, args.schedule_days))
        print(f"Scanning calendar {start.isoformat()}..{end.isoformat()}…")
        plan = client.query_schedule(start.isoformat(), end.isoformat())
        names = {name for _, name, _ in selected}
        programs_by_plan = {
            str(p.get("idInPlan")): p
            for p in (plan.get("programs") or [])
            if isinstance(p, dict)
        }
        for entity in plan.get("entities") or []:
            if not isinstance(entity, dict):
                continue
            program = programs_by_plan.get(str(entity.get("idInPlan")))
            name = str((program or {}).get("name") or "")
            sid = str(entity.get("id") or "")
            if not sid or name not in names:
                continue
            # If filtering bad-pace, inspect the scheduled program copy too.
            if args.bad_pace and program is not None and not _is_bad_pace(program):
                continue
            day = entity.get("happenDay")
            schedule_ids.append((sid, name, str(day)))
        print(f"Matched {len(schedule_ids)} calendar entries:")
        for sid, name, day in schedule_ids[:30]:
            print(f"  {day} {name} ({sid})")
        if len(schedule_ids) > 30:
            print(f"  … and {len(schedule_ids) - 30} more")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to delete.")
        return 0

    # Unschedule first so calendar copies go away before library deletes.
    for sid, name, day in schedule_ids:
        try:
            _unschedule(client, sid, start, end)
            print(f"unscheduled {day} {name}")
        except ToolError as error:
            print(f"unschedule failed {name}: {error}")

    ids = [wid for wid, _, _ in selected]
    for chunk in _chunked(ids, _DELETE_CHUNK):
        client.delete_programs(chunk)
        print(f"deleted {len(chunk)} workouts")

    print("Done.")
    return 0


def _unschedule(
    client: CorosClient, schedule_id: str, window_start: date, window_end: date
) -> None:
    """Minimal unschedule using the same versionObjects pattern as the MCP tool."""
    plan = client.query_schedule(window_start.isoformat(), window_end.isoformat())
    entity = next(
        (
            item
            for item in (plan.get("entities") or [])
            if isinstance(item, dict) and str(item.get("id")) == str(schedule_id)
        ),
        None,
    )
    if entity is None:
        raise ToolError(
            f"Scheduled workout {schedule_id!r} not found.",
            code="NOT_FOUND",
            hint="It may already have been removed.",
        )
    version_object: dict = {
        "id": str(entity["idInPlan"]),
        "status": 3,
    }
    if entity.get("planProgramId") is not None:
        version_object["planProgramId"] = str(entity["planProgramId"])
    if plan.get("id") is not None:
        version_object["planId"] = plan["id"]
    client.update_schedule({"versionObjects": [version_object], "pbVersion": 2})


if __name__ == "__main__":
    raise SystemExit(main())
