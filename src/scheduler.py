"""Job scheduling — detects due jobs, creates run instances, handles missed runs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Union

from src.models.job_types import (
    RecurringJob, ContinuousJob, OneTimeProject,
    RunHistory, RunStatus, MissedRunPolicy, RecurrencePattern, DayOfWeek
)

logger = logging.getLogger(__name__)

AnyJob = Union[RecurringJob, ContinuousJob, OneTimeProject]


_DAY_OF_WEEK_TO_WEEKDAY: dict[DayOfWeek, int] = {
    DayOfWeek.MONDAY: 0,
    DayOfWeek.TUESDAY: 1,
    DayOfWeek.WEDNESDAY: 2,
    DayOfWeek.THURSDAY: 3,
    DayOfWeek.FRIDAY: 4,
    DayOfWeek.SATURDAY: 5,
    DayOfWeek.SUNDAY: 6,
}


def _parse_interval(interval: str) -> timedelta:
    if interval.endswith("h"):
        return timedelta(hours=int(interval[:-1]))
    elif interval.endswith("m"):
        return timedelta(minutes=int(interval[:-1]))
    elif interval.endswith("d"):
        return timedelta(days=int(interval[:-1]))
    elif interval.endswith("s"):
        return timedelta(seconds=int(interval[:-1]))
    raise ValueError(f"Unknown interval format: {interval}")


def compute_next_run(job: RecurringJob, after: Optional[datetime] = None) -> Optional[datetime]:
    """
    Compute the next run time for a recurring job after the given datetime.
    Falls back to job.schedule.start_date if no history exists.
    """
    schedule = job.schedule
    now = after or datetime.now(timezone.utc)

    if schedule.end_date and now >= schedule.end_date:
        return None

    if schedule.recurrence_pattern == RecurrencePattern.CUSTOM:
        if schedule.interval:
            delta = _parse_interval(schedule.interval)
            return now + delta
        if schedule.cron_expression:
            # Placeholder: full cron parsing is not implemented.
            # When fully supported, this should parse the cron expression and
            # compute the next matching datetime after `now`.
            return now + timedelta(hours=1)

    if schedule.recurrence_pattern == RecurrencePattern.DAILY:
        next_dt = now + timedelta(days=1)
        if schedule.time_of_day:
            h, m = map(int, schedule.time_of_day.split(":"))
            next_dt = next_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        return next_dt

    if schedule.recurrence_pattern == RecurrencePattern.WEEKLY:
        target_days = [_DAY_OF_WEEK_TO_WEEKDAY[d] for d in schedule.days_of_week] if schedule.days_of_week else [0]
        for offset in range(1, 8):
            candidate = now + timedelta(days=offset)
            if candidate.weekday() in target_days:
                if schedule.time_of_day:
                    h, m = map(int, schedule.time_of_day.split(":"))
                    candidate = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                return candidate
        return now + timedelta(weeks=1)

    if schedule.recurrence_pattern == RecurrencePattern.MONTHLY:
        days = schedule.days_of_month or [1]
        next_month = (now.month % 12) + 1
        year = now.year if now.month < 12 else now.year + 1
        import calendar
        day = min(days[0], calendar.monthrange(year, next_month)[1])
        next_dt = now.replace(year=year, month=next_month, day=day, hour=0, minute=0, second=0, microsecond=0)
        if schedule.time_of_day:
            h, m = map(int, schedule.time_of_day.split(":"))
            next_dt = next_dt.replace(hour=h, minute=m)
        return next_dt

    return now + timedelta(days=1)


class JobScheduler:
    """
    Manages scheduling for recurring and continuous jobs.

    Parameters
    ----------
    jobs : list
        Initial list of jobs to manage.
    """

    def __init__(self, jobs: Optional[List[AnyJob]] = None) -> None:
        self.jobs: List[AnyJob] = jobs or []

    def add_job(self, job: AnyJob) -> None:
        """Register a job with the scheduler."""
        self.jobs.append(job)
        if isinstance(job, RecurringJob) and job.next_run_at is None:
            job.next_run_at = job.schedule.start_date

    def get_due_jobs(self, now: Optional[datetime] = None) -> List[AnyJob]:
        """Return jobs that are due to run right now."""
        now = now or datetime.now(timezone.utc)
        due = []
        for job in self.jobs:
            if job.is_paused:
                continue
            if isinstance(job, RecurringJob):
                if job.next_run_at and job.next_run_at <= now:
                    due.append(job)
            elif isinstance(job, ContinuousJob):
                # Continuous job is always "due" if not paused
                if job.started_at is None:
                    due.append(job)
                elif job.last_health_check is None:
                    due.append(job)
                else:
                    elapsed = (now - job.last_health_check).total_seconds()
                    if elapsed >= job.health_check_interval:
                        due.append(job)
        return due

    def create_run_instance(self, job: AnyJob) -> RunHistory:
        """Create a new run history entry and update next_run_at for recurring jobs."""
        run = RunHistory(started_at=datetime.now(timezone.utc))
        if isinstance(job, RecurringJob):
            job.run_history.append(run)
            job.next_run_at = compute_next_run(job, after=datetime.now(timezone.utc))
            logger.info(f"Recurring job '{job.name}': new run created. Next run at {job.next_run_at}")
        elif isinstance(job, ContinuousJob):
            if job.started_at is None:
                job.started_at = run.started_at
            job.last_health_check = run.started_at
            job.run_history.append(run)
        elif isinstance(job, OneTimeProject):
            job.run_history.append(run)
        return run

    def handle_missed_runs(self, job: RecurringJob, now: Optional[datetime] = None) -> List[RunHistory]:
        """
        Handle missed runs based on the job's missed_run_policy.
        Returns list of RunHistory records created.
        """
        now = now or datetime.now(timezone.utc)
        if job.next_run_at is None or job.next_run_at > now:
            return []

        missed = []
        check_time = job.next_run_at
        while check_time <= now:
            missed.append(check_time)
            check_time = compute_next_run(job, after=check_time)
            if check_time is None:
                break

        if not missed:
            return []

        policy = job.missed_run_policy
        runs_created = []

        if policy == MissedRunPolicy.SKIP:
            logger.info(f"Job '{job.name}': skipping {len(missed)} missed run(s).")
            job.next_run_at = compute_next_run(job, after=now)
        elif policy == MissedRunPolicy.RUN_IMMEDIATELY:
            for _ in missed:
                run = RunHistory(status=RunStatus.SUCCESS, summary="Missed run executed immediately")
                job.run_history.append(run)
                runs_created.append(run)
            job.next_run_at = compute_next_run(job, after=now)
        elif policy == MissedRunPolicy.RUN_LATEST_ONLY:
            run = RunHistory(status=RunStatus.SUCCESS, summary="Latest missed run executed")
            job.run_history.append(run)
            runs_created.append(run)
            job.next_run_at = compute_next_run(job, after=now)

        return runs_created

    def pause_job(self, job_id: str) -> bool:
        for job in self.jobs:
            if job.id == job_id:
                job.is_paused = True
                return True
        return False

    def resume_job(self, job_id: str) -> bool:
        for job in self.jobs:
            if job.id == job_id:
                job.is_paused = False
                return True
        return False
