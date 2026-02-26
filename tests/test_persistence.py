"""Tests for persistence (save/load checkpoint)."""

import json
from pathlib import Path

import pytest

from src.models.project import Project
from src.models.task import Task, TaskStatus
from src.persistence import save_checkpoint, load_checkpoint


def make_full_project() -> Project:
    p = Project(name="Full Project", description="A complete project", job_type="one_time")
    t1 = Task(name="T1", urgency=5, impact=4, description="First task")
    t2 = Task(name="T2", urgency=3, impact=3, dependencies=[t1.id])
    t1.status = TaskStatus.DONE
    p.tasks.extend([t1, t2])
    p.add_audit("created", "Project created")
    return p


class TestSaveCheckpoint:
    def test_creates_file(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        assert Path(path).exists()

    def test_creates_intermediate_dirs(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "subdir" / "deep" / "project.json")
        save_checkpoint(p, path)
        assert Path(path).exists()

    def test_valid_json_output(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        content = Path(path).read_text()
        data = json.loads(content)
        assert "id" in data
        assert "name" in data
        assert data["name"] == "Full Project"


class TestLoadCheckpoint:
    def test_roundtrip(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        loaded = load_checkpoint(path)
        assert loaded.id == p.id
        assert loaded.name == p.name

    def test_tasks_preserved(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        loaded = load_checkpoint(path)
        assert len(loaded.tasks) == 2
        assert loaded.tasks[0].name == "T1"
        assert loaded.tasks[0].status == TaskStatus.DONE

    def test_audit_log_preserved(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        loaded = load_checkpoint(path)
        assert len(loaded.audit_log) == 1
        assert loaded.audit_log[0].action == "created"

    def test_datetimes_timezone_aware(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        loaded = load_checkpoint(path)
        assert loaded.created_at.tzinfo is not None
        for task in loaded.tasks:
            assert task.created_at.tzinfo is not None

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_checkpoint(str(tmp_path / "nonexistent.json"))

    def test_priority_score_preserved(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        loaded = load_checkpoint(path)
        for orig, loaded_t in zip(p.tasks, loaded.tasks):
            assert loaded_t.priority_score == orig.priority_score

    def test_multiple_saves_latest_wins(self, tmp_path):
        p = make_full_project()
        path = str(tmp_path / "project.json")
        save_checkpoint(p, path)
        p.name = "Updated Project"
        save_checkpoint(p, path)
        loaded = load_checkpoint(path)
        assert loaded.name == "Updated Project"
