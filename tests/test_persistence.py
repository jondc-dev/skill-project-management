"""Tests for persistence module."""
import pytest
from src.models.project import Project
from src.models.task import Task, TaskStatus
from src.persistence import save_project, load_project, list_saved_projects, delete_project


def test_save_and_load(tmp_path):
    project = Project(name="Persist Test")
    t = Task(name="Saved Task", urgency=5, impact=4)
    project.tasks.append(t)
    project.log_action("test", "saving")

    save_project(project, str(tmp_path))
    loaded = load_project(project.id, str(tmp_path))

    assert loaded is not None
    assert loaded.id == project.id
    assert loaded.name == "Persist Test"
    assert len(loaded.tasks) == 1
    assert loaded.tasks[0].name == "Saved Task"
    assert len(loaded.audit_log) == 1


def test_load_nonexistent(tmp_path):
    result = load_project("nonexistent-id", str(tmp_path))
    assert result is None


def test_list_saved(tmp_path):
    p1 = Project(name="P1")
    p2 = Project(name="P2")
    save_project(p1, str(tmp_path))
    save_project(p2, str(tmp_path))
    ids = list_saved_projects(str(tmp_path))
    assert p1.id in ids
    assert p2.id in ids


def test_delete(tmp_path):
    p = Project(name="Delete Me")
    save_project(p, str(tmp_path))
    assert delete_project(p.id, str(tmp_path)) is True
    assert load_project(p.id, str(tmp_path)) is None
    assert delete_project(p.id, str(tmp_path)) is False


def test_roundtrip_preserves_tasks(tmp_path):
    project = Project(name="Roundtrip")
    t1 = Task(name="T1", status=TaskStatus.DONE, urgency=5, impact=3)
    t2 = Task(name="T2", status=TaskStatus.PENDING, urgency=2, impact=2)
    project.tasks = [t1, t2]
    save_project(project, str(tmp_path))
    loaded = load_project(project.id, str(tmp_path))
    assert loaded.tasks[0].status == TaskStatus.DONE
    assert loaded.tasks[1].status == TaskStatus.PENDING
