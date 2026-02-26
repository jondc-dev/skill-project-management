"""Tests for generate_status_report."""

import pytest

from src.models.project import Project, Risk
from src.models.task import Task, TaskStatus
from src.models.job_types import Schedule, RecurrencePattern, RunHistory
from src.reporting import generate_status_report
from datetime import datetime, timezone


def make_task(name="T", urgency=3, impact=3, status=TaskStatus.PENDING) -> Task:
    t = Task(name=name, urgency=urgency, impact=impact)
    t.status = status
    return t


class TestGenerateStatusReport:
    def test_returns_dict(self):
        p = Project(name="P")
        report = generate_status_report(p)
        assert isinstance(report, dict)

    def test_required_keys_present(self):
        p = Project(name="P")
        report = generate_status_report(p)
        assert "overall_progress_percent" in report
        assert "tasks_by_status" in report
        assert "blockers" in report
        assert "risks" in report
        assert "next_actions" in report
        assert "job_type_specific" in report

    def test_progress_percent(self):
        p = Project(name="P")
        p.tasks.append(make_task("T1", status=TaskStatus.DONE))
        p.tasks.append(make_task("T2", status=TaskStatus.PENDING))
        p.update_progress()
        report = generate_status_report(p)
        assert report["overall_progress_percent"] == 50.0

    def test_tasks_by_status_counts(self):
        p = Project(name="P")
        p.tasks.append(make_task("T1", status=TaskStatus.DONE))
        p.tasks.append(make_task("T2", status=TaskStatus.DONE))
        p.tasks.append(make_task("T3", status=TaskStatus.BLOCKED))
        report = generate_status_report(p)
        tbs = report["tasks_by_status"]
        assert tbs["done"] == 2
        assert tbs["blocked"] == 1
        assert tbs["pending"] == 0

    def test_blockers_list_blocked(self):
        p = Project(name="P")
        p.tasks.append(make_task("Blocker", status=TaskStatus.BLOCKED))
        p.tasks.append(make_task("Normal", status=TaskStatus.PENDING))
        report = generate_status_report(p)
        assert len(report["blockers"]) == 1
        assert report["blockers"][0]["name"] == "Blocker"

    def test_blockers_list_escalated(self):
        p = Project(name="P")
        p.tasks.append(make_task("Esc", status=TaskStatus.ESCALATED))
        report = generate_status_report(p)
        assert len(report["blockers"]) == 1

    def test_risks_only_open(self):
        p = Project(name="P")
        r1 = Risk(description="Open risk", probability=3, impact=3)
        r2 = Risk(description="Closed risk", probability=2, impact=2)
        r2.status = "closed"
        p.risks.extend([r1, r2])
        report = generate_status_report(p)
        assert len(report["risks"]) == 1
        assert report["risks"][0]["description"] == "Open risk"

    def test_next_actions_limit_5(self):
        p = Project(name="P")
        for i in range(10):
            p.tasks.append(make_task(f"T{i}", urgency=i % 5 + 1, impact=3))
        report = generate_status_report(p)
        assert len(report["next_actions"]) <= 5

    def test_next_actions_by_priority(self):
        p = Project(name="P")
        p.tasks.append(make_task("Low", urgency=1, impact=1))
        p.tasks.append(make_task("High", urgency=5, impact=5))
        report = generate_status_report(p)
        # Highest priority should appear first
        assert report["next_actions"][0]["name"] == "High"

    def test_next_actions_respects_dependencies(self):
        p = Project(name="P")
        t1 = Task(name="First", urgency=2, impact=2)
        t2 = Task(name="Second", urgency=5, impact=5, dependencies=[t1.id])
        p.tasks.extend([t1, t2])
        report = generate_status_report(p)
        # t2 cannot run until t1 is done; t1 should be first action
        first_name = report["next_actions"][0]["name"]
        assert first_name == "First"


class TestJobTypeSpecific:
    def test_one_time_job_type(self):
        p = Project(name="OneTime", job_type="one_time")
        report = generate_status_report(p)
        jts = report["job_type_specific"]
        assert "status" in jts
        assert "deadline" in jts

    def test_recurring_job_type(self):
        p = Project(name="Rec", job_type="recurring")
        p.schedule = Schedule(
            recurrence_pattern=RecurrencePattern.DAILY,
            start_date=datetime.now(timezone.utc),
        )
        report = generate_status_report(p)
        jts = report["job_type_specific"]
        assert "schedule" in jts
        assert "total_runs" in jts
        assert "last_run_status" in jts

    def test_recurring_last_run_status(self):
        from src.models.job_types import RunStatus
        p = Project(name="Rec", job_type="recurring")
        p.schedule = Schedule(
            recurrence_pattern=RecurrencePattern.WEEKLY,
            start_date=datetime.now(timezone.utc),
        )
        p.run_history.append(RunHistory(status=RunStatus.PARTIAL))
        report = generate_status_report(p)
        assert report["job_type_specific"]["last_run_status"] == "partial"

    def test_continuous_job_type_healthy(self):
        p = Project(name="Cont", job_type="continuous")
        p.tasks.append(make_task("T1", status=TaskStatus.DONE))
        report = generate_status_report(p)
        assert report["job_type_specific"]["health"] == "healthy"

    def test_continuous_job_type_degraded(self):
        p = Project(name="Cont", job_type="continuous")
        p.tasks.append(make_task("T1", status=TaskStatus.BLOCKED))
        report = generate_status_report(p)
        assert report["job_type_specific"]["health"] == "degraded"
