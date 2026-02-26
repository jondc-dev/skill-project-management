"""Tests for ExecutionLoop."""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.models.project import Project
from src.models.task import Task, TaskStatus
from src.engine.execution_loop import ExecutionLoop


def make_project(name="Test") -> Project:
    return Project(name=name)


def make_task(name="T1", urgency=3, impact=3, max_retries=2) -> Task:
    return Task(name=name, urgency=urgency, impact=impact, max_retries=max_retries)


class TestExecutionLoopBasic:
    def test_always_succeeds_with_default_executor(self):
        p = make_project()
        t = make_task()
        p.tasks.append(t)
        loop = ExecutionLoop(project=p)
        result = loop.run()
        assert t.status == TaskStatus.DONE
        assert result.overall_progress_percent == 100.0

    def test_custom_executor_called(self):
        p = make_project()
        t = make_task()
        p.tasks.append(t)
        executor = MagicMock(return_value=True)
        loop = ExecutionLoop(project=p, task_executor=executor)
        loop.run()
        executor.assert_called()

    def test_all_tasks_complete_sequentially(self):
        p = make_project()
        for i in range(3):
            p.tasks.append(make_task(name=f"T{i}"))
        loop = ExecutionLoop(project=p)
        loop.run()
        for t in p.tasks:
            assert t.status == TaskStatus.DONE

    def test_progress_100_after_all_done(self):
        p = make_project()
        p.tasks.append(make_task())
        loop = ExecutionLoop(project=p)
        loop.run()
        assert p.overall_progress_percent == 100.0

    def test_audit_log_populated(self):
        p = make_project()
        p.tasks.append(make_task())
        loop = ExecutionLoop(project=p)
        loop.run()
        actions = [e.action for e in p.audit_log]
        assert "task_completed" in actions


class TestExecutionLoopDependencies:
    def test_dependency_order_respected(self):
        execution_order = []
        p = make_project()
        t1 = Task(name="First", urgency=2, impact=2)
        t2 = Task(name="Second", urgency=3, impact=3, dependencies=[t1.id])
        p.tasks.extend([t2, t1])  # add in reverse order

        def executor(task):
            execution_order.append(task.name)
            return True

        loop = ExecutionLoop(project=p, task_executor=executor)
        loop.run()
        assert execution_order.index("First") < execution_order.index("Second")

    def test_task_with_unmet_dependency_skipped(self):
        p = make_project()
        t1 = Task(name="Blocked", urgency=5, impact=5, dependencies=["nonexistent-id"])
        p.tasks.append(t1)
        loop = ExecutionLoop(project=p)
        loop.run()
        # task cannot run; stays pending (not done)
        assert t1.status != TaskStatus.DONE


class TestExecutionLoopRetry:
    def test_retry_on_failure(self):
        call_count = {"n": 0}

        def flaky(task):
            call_count["n"] += 1
            return call_count["n"] >= 3  # succeed on 3rd attempt

        p = make_project()
        t = Task(name="Flaky", urgency=3, impact=3, max_retries=3)
        p.tasks.append(t)

        with patch("time.sleep"):  # skip actual delays
            loop = ExecutionLoop(project=p, task_executor=flaky)
            loop.run()

        assert t.status == TaskStatus.DONE
        assert call_count["n"] >= 3

    def test_retry_count_incremented(self):
        p = make_project()
        t = Task(name="AlwaysFail", urgency=3, impact=3, max_retries=2)
        p.tasks.append(t)

        with patch("time.sleep"):
            loop = ExecutionLoop(project=p, task_executor=lambda _: False)
            loop.run()

        assert t.retry_count > 0

    def test_exhausted_retries_marks_blocked_or_escalated(self):
        p = make_project()
        t = Task(name="Doomed", urgency=3, impact=3, max_retries=1)
        p.tasks.append(t)

        with patch("time.sleep"):
            loop = ExecutionLoop(project=p, task_executor=lambda _: False)
            loop.run()

        assert t.status in (TaskStatus.BLOCKED, TaskStatus.ESCALATED)

    def test_exponential_backoff_delays(self):
        delays = []
        original_sleep = time.sleep

        def capture_sleep(n):
            delays.append(n)

        p = make_project()
        t = Task(name="Retry", urgency=3, impact=3, max_retries=3)
        p.tasks.append(t)

        with patch("time.sleep", side_effect=capture_sleep):
            loop = ExecutionLoop(project=p, task_executor=lambda _: False)
            loop.run()

        # Should have increasing delays
        assert len(delays) >= 1
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]


class TestExecutionLoopAlternatives:
    def test_alternative_strategy_tried(self):
        call_count = {"n": 0}

        def executor(task):
            call_count["n"] += 1
            # fail primary retries, succeed on alternative call
            return call_count["n"] > 4

        p = make_project()
        t = Task(
            name="AltTask",
            urgency=3,
            impact=3,
            max_retries=2,
            alternative_strategies=["Plan B"],
        )
        p.tasks.append(t)

        with patch("time.sleep"):
            loop = ExecutionLoop(project=p, task_executor=executor)
            loop.run()

        actions = [e.action for e in p.audit_log]
        assert "alternative_strategy" in actions

    def test_escalation_when_all_alternatives_fail(self):
        p = make_project()
        t = Task(
            name="EscalateMe",
            urgency=3,
            impact=3,
            max_retries=1,
            alternative_strategies=["B", "C"],
        )
        p.tasks.append(t)

        with patch("time.sleep"):
            loop = ExecutionLoop(project=p, task_executor=lambda _: False)
            loop.run()

        assert t.status == TaskStatus.ESCALATED
        assert len(loop.escalations) == 1


class TestExecutionLoopCheckpoint:
    def test_checkpoint_saved(self, tmp_path):
        p = make_project()
        p.tasks.append(make_task())
        path = str(tmp_path / "checkpoint.json")
        loop = ExecutionLoop(project=p, checkpoint_path=path)
        loop.run()
        import os
        assert os.path.exists(path)
