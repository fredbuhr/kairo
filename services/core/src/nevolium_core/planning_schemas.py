from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .schemas import TaskRead


TodayBucket = Literal[
    "overdue",
    "in_progress",
    "due_today",
    "planned",
    "completed_today",
    "backlog",
]


class PlannedTaskRead(TaskRead):
    priority: int
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    due_at: datetime | None


class TaskPlanningUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=320)
    description: str | None = Field(default=None, max_length=16000)
    status: Literal["todo", "completed"] | None = None
    priority: int | None = Field(default=None, ge=0, le=4)
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    due_at: datetime | None = None

    @field_validator("planned_start_at", "planned_end_at", "due_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("planning timestamps must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_supplied_window(self) -> "TaskPlanningUpdate":
        if (
            self.planned_start_at is not None
            and self.planned_end_at is not None
            and self.planned_end_at < self.planned_start_at
        ):
            raise ValueError("planned_end_at must be on or after planned_start_at")
        return self


class TodayTaskItem(BaseModel):
    bucket: TodayBucket
    project_id: str
    project_name: str
    task: PlannedTaskRead


class TodayRead(BaseModel):
    next_cursors: dict[str, str] = Field(default_factory=dict)
    day: date
    timezone: str
    day_start: datetime
    day_end: datetime
    overdue: list[TodayTaskItem] = Field(default_factory=list)
    in_progress: list[TodayTaskItem] = Field(default_factory=list)
    due_today: list[TodayTaskItem] = Field(default_factory=list)
    planned: list[TodayTaskItem] = Field(default_factory=list)
    completed_today: list[TodayTaskItem] = Field(default_factory=list)
    backlog: list[TodayTaskItem] = Field(default_factory=list)
