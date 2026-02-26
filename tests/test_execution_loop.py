"""Tests for execution loop."""
import pytest
from src.models.project import Project, ProjectPhase
from src.models.task import Task, TaskStatus
from src.engine.execution_loop import ExecutionLoop


def always_succeed(task: Task) -> bool:
    return True


def always_fail(task: Task) -> bool:
    return False


def test_execution_simple(tmp_path):
    project = Project(name="Simple")
    t1 = Task(name="Task 1")
    t2 = Task(name="Task 2")
    project.tasks = [t1, t2]

    loop = ExecutionLoop(project, always_succeed, persistence_path=str(tmp_path), base_delay=0.0)
    loop.run()

    assert all(t.status == TaskStatus.DONE for t in project.tasks)
    assert project.phase == ProjectPhase.CLOSURE


def test_execution_with_dependency(tmp_path):
    project = Project(name="Deps")
    t1 = Task(name="First")
    t2 = Task(name="Second", dependencies=[t1.id])
    project.tasks = [t1, t2]

    loop = ExecutionLoop(project, always_succeed, persistence_path=str(tmp_path), base_delay=0.0)
    loop.run()

    assert t1.status == TaskStatus.DONE
    assert t2.status == TaskStatus.DONE


def test_execution_failure_escalates(tmp_path):
    project = Project(name="Fail")
    t1 = Task(name="Failing Task", max_retries=2)
    project.tasks = [t1]

    loop = ExecutionLoop(project, always_fail, persistence_path=str(tmp_path), base_delay=0.0)
    loop.run(max_iterations=50)

    assert t1.status == TaskStatus.ESCALATED


def test_execution_creates_checkpoint(tmp_path):
    project = Project(name="Checkpoint Test")
    t1 = Task(name="T1")
    project.tasks = [t1]

    loop = ExecutionLoop(project, always_succeed, persistence_path=str(tmp_path), base_delay=0.0)
    loop.run()

    files = list(tmp_path.glob("project_*.json"))
    assert len(files) == 1
