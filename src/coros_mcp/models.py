from __future__ import annotations

from typing import Literal

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
    count: int | None = None
    steps: list[WorkoutStep] | None = None


class WorkoutCreate(BaseModel):
    name: str
    sport: str
    steps: list[WorkoutStep] = Field(default_factory=list)
