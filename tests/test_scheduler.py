"""Tests for JobScheduler."""

from datetime import datetime, timedelta, timezone

import pytest

from src.models.project import Project
from src.models.job_types import Schedule, RecurrencePattern
from src.scheduler import JobScheduler


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_schedule(pattern=RecurrencePattern.DAILY, next_run_offset_seconds=0) -> Schedule:
    return Schedule(
        recurrence_pattern=pattern,
        start_date=utcnow(),
        next_run_at=utcnow() + timedelta(seconds=next_run_offset_seconds),
    )


def make_recurring_project(pattern=RecurrencePattern.DAILY, offset_seconds=0) -> Project:
    p = Project(name="Recurring", job_type="recurring")
    p.schedule = make_schedule(pattern, offset_seconds)
    return p


class TestGetDueJobs:
    def test_past_next_run_is_due(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-60)  # 1 min ago
        assert p in scheduler.get_due_jobs([p])

    def test_future_next_run_not_due(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=3600)  # 1 hour from now
        assert p not in scheduler.get_due_jobs([p])

    def test_no_schedule_not_included(self):
        scheduler = JobScheduler()
        p = Project(name="OneTime")
        assert p not in scheduler.get_due_jobs([p])

    def test_next_run_none_not_included(self):
        scheduler = JobScheduler()
        p = Project(name="Recurring", job_type="recurring")
        p.schedule = Schedule(
            recurrence_pattern=RecurrencePattern.DAILY,
            start_date=utcnow(),
            next_run_at=None,
        )
        assert p not in scheduler.get_due_jobs([p])

    def test_multiple_projects_filtered(self):
        scheduler = JobScheduler()
        due = make_recurring_project(offset_seconds=-1)
        not_due = make_recurring_project(offset_seconds=3600)
        result = scheduler.get_due_jobs([due, not_due])
        assert due in result
        assert not_due not in result


class TestCalculateNextRun:
    def test_daily_adds_one_day(self):
        scheduler = JobScheduler()
        s = Schedule(
            recurrence_pattern=RecurrencePattern.DAILY,
            start_date=utcnow(),
            interval=1,
        )
        before = utcnow()
        nxt = scheduler.calculate_next_run(s)
        assert nxt > before + timedelta(hours=23)
        assert nxt < before + timedelta(hours=25)

    def test_daily_interval_2(self):
        scheduler = JobScheduler()
        s = Schedule(
            recurrence_pattern=RecurrencePattern.DAILY,
            start_date=utcnow(),
            interval=2,
        )
        before = utcnow()
        nxt = scheduler.calculate_next_run(s)
        assert nxt > before + timedelta(days=1)

    def test_weekly_adds_seven_days(self):
        scheduler = JobScheduler()
        s = Schedule(
            recurrence_pattern=RecurrencePattern.WEEKLY,
            start_date=utcnow(),
            interval=1,
        )
        before = utcnow()
        nxt = scheduler.calculate_next_run(s)
        assert nxt > before + timedelta(days=6)
        assert nxt < before + timedelta(days=8)

    def test_monthly_adds_approx_30_days(self):
        scheduler = JobScheduler()
        s = Schedule(
            recurrence_pattern=RecurrencePattern.MONTHLY,
            start_date=utcnow(),
            interval=1,
        )
        before = utcnow()
        nxt = scheduler.calculate_next_run(s)
        assert nxt > before + timedelta(days=29)
        assert nxt < before + timedelta(days=31)

    def test_custom_pattern_returns_future(self):
        scheduler = JobScheduler()
        s = Schedule(
            recurrence_pattern=RecurrencePattern.CUSTOM,
            start_date=utcnow(),
            interval=3,
        )
        before = utcnow()
        nxt = scheduler.calculate_next_run(s)
        assert nxt > before


class TestCreateRunInstance:
    def test_resets_task_statuses(self):
        from src.models.task import Task, TaskStatus

        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-1)
        t = Task(name="T1", urgency=3, impact=3)
        t.status = TaskStatus.DONE
        p.tasks.append(t)
        scheduler.create_run_instance(p)
        assert p.tasks[0].status == TaskStatus.PENDING

    def test_run_history_appended(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-1)
        assert len(p.run_history) == 0
        scheduler.create_run_instance(p)
        assert len(p.run_history) == 1

    def test_next_run_advanced(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-1)
        old_next = p.schedule.next_run_at
        scheduler.create_run_instance(p)
        assert p.schedule.next_run_at > old_next

    def test_progress_reset(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-1)
        p.overall_progress_percent = 75.0
        scheduler.create_run_instance(p)
        assert p.overall_progress_percent == 0.0


class TestHandleMissedRuns:
    def test_skip_policy_advances_next_run(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-3600)
        old_next = p.schedule.next_run_at
        scheduler.handle_missed_runs(p, policy="skip")
        assert p.schedule.next_run_at > old_next

    def test_run_immediately_creates_run(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-3600)
        scheduler.handle_missed_runs(p, policy="run_immediately")
        assert len(p.run_history) == 1

    def test_run_latest_only_creates_run(self):
        scheduler = JobScheduler()
        p = make_recurring_project(offset_seconds=-3600)
        scheduler.handle_missed_runs(p, policy="run_latest_only")
        assert len(p.run_history) == 1

    def test_no_schedule_is_noop(self):
        scheduler = JobScheduler()
        p = Project(name="OneTime")
        # Should not raise
        scheduler.handle_missed_runs(p)
