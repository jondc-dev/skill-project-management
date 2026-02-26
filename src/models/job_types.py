"""Job type models: Schedule, RunHistory, and related enums."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class RecurrencePattern(str, Enum):
    """How often a recurring job repeats."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class RunStatus(str, Enum):
    """Outcome status of a single run execution."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class Schedule(BaseModel):
    """Defines when and how often a recurring job runs.

    Attributes:
        recurrence_pattern: Frequency category.
        days_of_week: For weekly patterns; 0=Monday … 6=Sunday.
        days_of_month: For monthly patterns.
        time_of_day: Clock time in HH:MM format.
        interval: Run every N units (e.g. every 2 weeks).
        cron_expression: Optional cron string for CUSTOM patterns.
        start_date: First eligible run date (timezone-aware).
        end_date: Last eligible run date (timezone-aware), or None.
        timezone: IANA timezone name (default "UTC").
        next_run_at: Pre-computed next execution datetime.
    """

    recurrence_pattern: RecurrencePattern
    days_of_week: list[int] = Field(default_factory=list)
    days_of_month: list[int] = Field(default_factory=list)
    time_of_day: str = "09:00"
    interval: int = 1
    cron_expression: str | None = None
    start_date: datetime
    end_date: datetime | None = None
    timezone: str = "UTC"
    next_run_at: datetime | None = None


class RunHistory(BaseModel):
    """Record of a single job execution.

    Attributes:
        run_id: Unique identifier for this run.
        started_at: When execution began (timezone-aware).
        completed_at: When execution finished, or None if ongoing.
        status: Outcome of the run.
        summary: Human-readable summary text.
        tasks_completed: Count of tasks that finished successfully.
        tasks_failed: Count of tasks that failed.
    """

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.SUCCESS
    summary: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
