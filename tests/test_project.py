"""Tests for Project model."""

from datetime import datetime, timezone

import pytest

from src.models.project import Project, ProjectPhase, ProjectStatus, Risk, AuditEntry
from src.models.task import Task, TaskStatus


def make_project(**kwargs) -> Project:
    defaults = dict(name="Test Project")
    defaults.update(kwargs)
    return Project(**defaults)


def make_task(name="T1", urgency=3, impact=3, status=TaskStatus.PENDING) -> Task:
    t = Task(name=name, urgency=urgency, impact=impact)
    t.status = status
    return t


class TestProjectCreation:
    def test_defaults(self):
        p = make_project()
        assert p.status == ProjectStatus.ACTIVE
        assert p.phase == ProjectPhase.INITIATION
        assert p.tasks == []
        assert p.risks == []
        assert p.audit_log == []
        assert p.overall_progress_percent == 0.0
        assert p.job_type == "one_time"

    def test_id_generated(self):
        p1 = make_project()
        p2 = make_project()
        assert p1.id != p2.id

    def test_created_at_timezone_aware(self):
        p = make_project()
        assert p.created_at.tzinfo is not None

    def test_deadline_optional(self):
        p = make_project()
        assert p.deadline is None

    def test_deadline_set(self):
        dl = datetime(2025, 12, 31, tzinfo=timezone.utc)
        p = make_project(deadline=dl)
        assert p.deadline == dl


class TestRisk:
    def test_risk_score_computed(self):
        r = Risk(description="Outage", probability=4, impact=5)
        assert r.risk_score == 20

    def test_risk_score_min(self):
        r = Risk(description="Minor", probability=1, impact=1)
        assert r.risk_score == 1

    def test_risk_default_status_open(self):
        r = Risk(description="Test", probability=2, impact=2)
        assert r.status == "open"

    def test_risk_id_generated(self):
        r1 = Risk(description="R1", probability=1, impact=1)
        r2 = Risk(description="R2", probability=1, impact=1)
        assert r1.id != r2.id


class TestProjectTasks:
    def test_add_task(self):
        p = make_project()
        t = make_task()
        p.tasks.append(t)
        assert len(p.tasks) == 1

    def test_update_progress_no_tasks(self):
        p = make_project()
        p.update_progress()
        assert p.overall_progress_percent == 0.0

    def test_update_progress_all_done(self):
        p = make_project()
        for i in range(4):
            t = make_task(name=f"T{i}", status=TaskStatus.DONE)
            p.tasks.append(t)
        p.update_progress()
        assert p.overall_progress_percent == 100.0

    def test_update_progress_partial(self):
        p = make_project()
        p.tasks.append(make_task(name="T1", status=TaskStatus.DONE))
        p.tasks.append(make_task(name="T2", status=TaskStatus.PENDING))
        p.tasks.append(make_task(name="T3", status=TaskStatus.PENDING))
        p.tasks.append(make_task(name="T4", status=TaskStatus.DONE))
        p.update_progress()
        assert p.overall_progress_percent == 50.0

    def test_update_progress_none_done(self):
        p = make_project()
        p.tasks.append(make_task())
        p.update_progress()
        assert p.overall_progress_percent == 0.0


class TestProjectPhase:
    def test_phase_default_initiation(self):
        p = make_project()
        assert p.phase == ProjectPhase.INITIATION

    def test_phase_enum_values(self):
        phases = [e.value for e in ProjectPhase]
        assert "initiation" in phases
        assert "closure" in phases


class TestAuditLog:
    def test_add_audit(self):
        p = make_project()
        p.add_audit("task_added", "Added T1")
        assert len(p.audit_log) == 1
        entry = p.audit_log[0]
        assert entry.action == "task_added"
        assert entry.details == "Added T1"
        assert entry.actor == "system"

    def test_audit_timestamp_timezone_aware(self):
        p = make_project()
        p.add_audit("test", "")
        assert p.audit_log[0].timestamp.tzinfo is not None

    def test_multiple_audit_entries(self):
        p = make_project()
        p.add_audit("created", "")
        p.add_audit("task_added", "T1")
        p.add_audit("phase_advanced", "planning")
        assert len(p.audit_log) == 3

    def test_audit_custom_actor(self):
        p = make_project()
        p.add_audit("manual_action", "Override", actor="human")
        assert p.audit_log[0].actor == "human"


class TestProjectStatus:
    def test_status_transitions(self):
        p = make_project()
        for status in ProjectStatus:
            p.status = status
            assert p.status == status
