from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class JobType(str, Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    CONTINUOUS = "continuous"


class RecurrencePattern(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class MissedRunPolicy(str, Enum):
    SKIP = "skip"
    RUN_IMMEDIATELY = "run_immediately"
    RUN_LATEST_ONLY = "run_latest_only"


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class RunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class Schedule(BaseModel):
    recurrence_pattern: RecurrencePattern = RecurrencePattern.DAILY
    days_of_week: List[DayOfWeek] = Field(default_factory=list)
    days_of_month: List[int] = Field(default_factory=list)
    time_of_day: Optional[str] = None  # "HH:MM"
    interval: Optional[str] = None     # e.g., "4h", "3d"
    cron_expression: Optional[str] = None
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None
    timezone: str = "UTC"


class RunHistory(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: RunStatus = RunStatus.SUCCESS
    summary: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0


class JobBase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    job_type: JobType
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_paused: bool = False


class OneTimeProject(JobBase):
    job_type: JobType = JobType.ONE_TIME
    deadline: Optional[datetime] = None
    run_history: List[RunHistory] = Field(default_factory=list)


class RecurringJob(JobBase):
    job_type: JobType = JobType.RECURRING
    schedule: Schedule
    missed_run_policy: MissedRunPolicy = MissedRunPolicy.RUN_LATEST_ONLY
    run_history: List[RunHistory] = Field(default_factory=list)
    next_run_at: Optional[datetime] = None
    task_template: List[dict] = Field(default_factory=list)  # template tasks as dicts


class ContinuousJob(JobBase):
    job_type: JobType = JobType.CONTINUOUS
    health_check_interval: int = 300  # seconds
    last_health_check: Optional[datetime] = None
    health_status: str = "healthy"
    started_at: Optional[datetime] = None
    run_history: List[RunHistory] = Field(default_factory=list)

    @property
    def uptime_seconds(self) -> Optional[float]:
        if self.started_at is None:
            return None
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()
