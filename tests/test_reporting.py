"""Tests for reporting module."""
import pytest
from src.models.project import Project
from src.models.task import Task, TaskStatus
from src.models.job_types import RecurringJob, ContinuousJob, Schedule, RecurrencePattern
from src.reporting import (
    get_status_report, get_task_summary,
    get_recurring_job_report, get_continuous_job_report
)
from datetime import datetime, timezone


def test_status_report_structure():
    p = Project(name="Report Test")
    t = Task(name="Task A", status=TaskStatus.PENDING, urgency=3, impact=3)
    p.tasks.append(t)
    report = get_status_report(p)
    assert "overall_progress_percent" in report
    assert "tasks_by_status" in report
    assert "blockers" in report
    assert "next_actions" in report
    assert report["name"] == "Report Test"


def test_status_report_progress():
    p = Project(name="P")
    t1 = Task(name="Done", status=TaskStatus.DONE)
    t2 = Task(name="Pending", status=TaskStatus.PENDING)
    p.tasks = [t1, t2]
    report = get_status_report(p)
    assert report["overall_progress_percent"] == 50.0


def test_task_summary_grouped():
    p = Project(name="P")
    t1 = Task(name="A", status=TaskStatus.DONE, urgency=5, impact=5)
    t2 = Task(name="B", status=TaskStatus.PENDING, urgency=2, impact=2)
    t3 = Task(name="C", status=TaskStatus.PENDING, urgency=4, impact=4)
    p.tasks = [t1, t2, t3]
    summary = get_task_summary(p)
    assert len(summary["done"]) == 1
    assert len(summary["pending"]) == 2
    # C has higher priority (16 vs 4), so it should be first
    assert summary["pending"][0]["name"] == "C"


def test_recurring_job_report():
    now = datetime.now(timezone.utc)
    schedule = Schedule(recurrence_pattern=RecurrencePattern.DAILY, start_date=now)
    job = RecurringJob(name="Daily Job", schedule=schedule)
    report = get_recurring_job_report(job)
    assert report["name"] == "Daily Job"
    assert "success_rate" in report
    assert "next_scheduled_run" in report


def test_continuous_job_report():
    job = ContinuousJob(name="Monitor", health_check_interval=60)
    job.started_at = datetime.now(timezone.utc)
    report = get_continuous_job_report(job)
    assert report["name"] == "Monitor"
    assert "uptime_seconds" in report
    assert report["health_status"] == "healthy"
