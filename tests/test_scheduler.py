"""Tests for job scheduler."""
import pytest
from datetime import datetime, timezone, timedelta
from src.models.job_types import (
    RecurringJob, ContinuousJob, Schedule, RecurrencePattern, MissedRunPolicy, RunStatus
)
from src.scheduler import JobScheduler, compute_next_run


def make_recurring_job(pattern=RecurrencePattern.DAILY, policy=MissedRunPolicy.RUN_LATEST_ONLY):
    now = datetime.now(timezone.utc)
    schedule = Schedule(recurrence_pattern=pattern, start_date=now)
    job = RecurringJob(name="Test Recurring", schedule=schedule, missed_run_policy=policy)
    job.next_run_at = now - timedelta(hours=1)  # already due
    return job


def test_get_due_jobs():
    scheduler = JobScheduler()
    job = make_recurring_job()
    scheduler.add_job(job)
    due = scheduler.get_due_jobs()
    assert job in due


def test_paused_job_not_due():
    scheduler = JobScheduler()
    job = make_recurring_job()
    job.is_paused = True
    scheduler.add_job(job)
    due = scheduler.get_due_jobs()
    assert job not in due


def test_create_run_instance_recurring():
    scheduler = JobScheduler()
    job = make_recurring_job()
    run = scheduler.create_run_instance(job)
    assert len(job.run_history) == 1
    assert job.next_run_at is not None


def test_missed_run_skip():
    scheduler = JobScheduler()
    job = make_recurring_job(policy=MissedRunPolicy.SKIP)
    job.next_run_at = datetime.now(timezone.utc) - timedelta(days=3)
    runs = scheduler.handle_missed_runs(job)
    assert runs == []  # skip policy creates no runs


def test_missed_run_run_latest_only():
    scheduler = JobScheduler()
    job = make_recurring_job(policy=MissedRunPolicy.RUN_LATEST_ONLY)
    job.next_run_at = datetime.now(timezone.utc) - timedelta(days=3)
    runs = scheduler.handle_missed_runs(job)
    assert len(runs) == 1


def test_missed_run_run_immediately():
    scheduler = JobScheduler()
    job = make_recurring_job(policy=MissedRunPolicy.RUN_IMMEDIATELY)
    job.next_run_at = datetime.now(timezone.utc) - timedelta(days=3)
    runs = scheduler.handle_missed_runs(job)
    assert len(runs) >= 1


def test_pause_resume():
    scheduler = JobScheduler()
    job = make_recurring_job()
    scheduler.add_job(job)
    assert scheduler.pause_job(job.id) is True
    assert job.is_paused is True
    assert scheduler.resume_job(job.id) is True
    assert job.is_paused is False


def test_continuous_job_due_on_start():
    scheduler = JobScheduler()
    job = ContinuousJob(name="Monitor", health_check_interval=10)
    scheduler.add_job(job)
    due = scheduler.get_due_jobs()
    assert job in due


def test_compute_next_run_daily():
    now = datetime.now(timezone.utc)
    schedule = Schedule(recurrence_pattern=RecurrencePattern.DAILY, start_date=now)
    job = RecurringJob(name="Daily", schedule=schedule)
    next_run = compute_next_run(job, after=now)
    assert next_run is not None
    assert next_run > now


def test_compute_next_run_custom_interval():
    now = datetime.now(timezone.utc)
    schedule = Schedule(recurrence_pattern=RecurrencePattern.CUSTOM, interval="4h", start_date=now)
    job = RecurringJob(name="Custom", schedule=schedule)
    next_run = compute_next_run(job, after=now)
    assert next_run == now + timedelta(hours=4)
