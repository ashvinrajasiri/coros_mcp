#!/usr/bin/env python3
"""Live smoke test against COROS Training Hub (same tools Hermes will call).

Requires local .env:
  COROS_EMAIL=...
  COROS_PASSWORD=...
  COROS_REGION=us

Creates a uniquely named test workout, schedules it for tomorrow, verifies it,
then unschedules and deletes it. Does not print secrets.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def step(title: str) -> None:
    print(f"\n==> {title}")


def fail_if_error(label: str, result: object) -> dict:
    if not isinstance(result, dict):
        raise RuntimeError(f"{label}: expected dict, got {type(result)}")
    if result.get("error"):
        raise RuntimeError(
            f"{label}: {result.get('code')} — {result.get('error')} "
            f"(hint={result.get('hint')})"
        )
    return result


def main() -> int:
    from coros_mcp.config import ConfigError, load_config
    from coros_mcp import server

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"FAIL config: {exc}")
        print("Edit .env (copied from .env.example) with your COROS login.")
        return 1

    print(f"Region: {cfg.region}")
    email = cfg.email
    masked = f"{email[:2]}…@{email.split('@')[-1]}" if "@" in email else "(set)"
    print(f"Email: {masked}")

    server._reset_client()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    start_14 = today - timedelta(days=14)
    stamp = today.strftime("%Y%m%d-%H%M%S")
    workout_name = f"coros_mcp smoke {stamp}"
    workout_id: str | None = None
    schedule_id: str | None = None

    try:
        step("1. get_daily_metrics (today)")
        metrics = fail_if_error(
            "metrics",
            server.get_daily_metrics(today.isoformat(), today.isoformat()),
        )
        days = metrics.get("days") or []
        print(f"OK days={len(days)}")

        step("2. list_activities (last 14 days)")
        activities = fail_if_error(
            "activities",
            server.list_activities(start_14.isoformat(), today.isoformat()),
        )
        acts = activities.get("activities") or []
        print(f"OK activities={len(acts)}")
        if acts:
            print(f"   sample={acts[0].get('title')!r} sport={acts[0].get('sport')!r}")

        step("3. create_workout (easy run)")
        created = fail_if_error(
            "create",
            server.create_workout(
                name=workout_name,
                sport="run",
                steps=[
                    {"type": "warmup", "duration": {"unit": "time", "value": 5, "time_unit": "min"}},
                    {"type": "steady", "duration": {"unit": "time", "value": 20, "time_unit": "min"}},
                    {"type": "cooldown", "duration": {"unit": "time", "value": 5, "time_unit": "min"}},
                ],
            ),
        )
        workout_id = str(created.get("id") or "")
        if not workout_id:
            raise RuntimeError(f"create returned no id: {created}")
        print(f"OK workout_id={workout_id}")

        step("4. schedule_workout (tomorrow)")
        scheduled = fail_if_error(
            "schedule",
            server.schedule_workout(workout_id, tomorrow.isoformat()),
        )
        print(f"OK schedule={scheduled}")

        step("5. list_scheduled_workouts (tomorrow)")
        listed = fail_if_error(
            "list_scheduled",
            server.list_scheduled_workouts(tomorrow.isoformat(), tomorrow.isoformat()),
        )
        entries = listed.get("scheduled") or []
        print(f"OK scheduled_count={len(entries)}")
        for entry in entries:
            name = str(entry.get("name") or "")
            if workout_name in name or str(entry.get("workout_id")) == workout_id:
                schedule_id = str(entry.get("schedule_id") or entry.get("id") or "")
                print(f"   matched schedule_id={schedule_id} name={name!r}")
                break
        if not schedule_id and entries:
            schedule_id = str(entries[0].get("schedule_id") or entries[0].get("id") or "")
            print(f"   fallback schedule_id={schedule_id}")

        if not schedule_id:
            raise RuntimeError(
                "Workout created/scheduled but could not find it on tomorrow's calendar. "
                "Check COROS Training Hub manually — API shape may need a tweak."
            )

        step("6. cleanup unschedule + delete")
        fail_if_error("unschedule", server.unschedule_workout(schedule_id))
        print("OK unscheduled")
        fail_if_error("delete", server.delete_workout(workout_id))
        print("OK deleted")
        workout_id = None

        print("\nSUCCESS — live smoke test passed.")
        print("Safe to push after you optionally glance at Training Hub.")
        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL {type(exc).__name__}: {exc}")
        if workout_id:
            print(f"Leftover library workout id={workout_id} name={workout_name!r}")
            print("You may want to delete it in COROS Training Hub if cleanup failed.")
        return 2
    finally:
        server._reset_client()


if __name__ == "__main__":
    sys.exit(main())
