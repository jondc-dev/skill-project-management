"""Tests for project model."""
import pytest
from src.models.project import Project, ProjectPhase, ProjectStatus, Risk, RiskStatus
from src.models.task import Task, TaskStatus


def test_project_creation():
    p = Project(name="Test Project")
    assert p.name == "Test Project"
    assert p.phase == ProjectPhase.INITIATION
    assert p.status == ProjectStatus.ACTIVE


def test_project_progress_empty():
    p = Project(name="Empty")
    assert p.overall_progress_percent == 0.0


def test_project_progress():
    t1 = Task(name="A", status=TaskStatus.DONE)
    t2 = Task(name="B", status=TaskStatus.DONE)
    t3 = Task(name="C", status=TaskStatus.PENDING)
    p = Project(name="P", tasks=[t1, t2, t3])
    assert p.overall_progress_percent == pytest.approx(66.7, abs=0.1)


def test_advance_phase():
    p = Project(name="P")
    assert p.phase == ProjectPhase.INITIATION
    p.advance_phase()
    assert p.phase == ProjectPhase.PLANNING
    p.advance_phase()
    assert p.phase == ProjectPhase.EXECUTION


def test_log_action():
    p = Project(name="P")
    p.log_action("test_actor", "did something", {"key": "value"})
    assert len(p.audit_log) == 1
    entry = p.audit_log[0]
    assert entry.actor == "test_actor"
    assert entry.description == "did something"
    assert entry.details == {"key": "value"}


def test_risk_score():
    r = Risk(description="Server failure", probability=4, impact=5)
    assert r.risk_score == 20


def test_risk_status_default():
    r = Risk(description="Network issue", probability=2, impact=3)
    assert r.status == RiskStatus.IDENTIFIED
