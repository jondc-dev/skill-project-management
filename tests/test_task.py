"""Tests for task model."""
import pytest
from src.models.task import Task, TaskStatus, RetryStrategy, EscalationMessage, sort_tasks_by_priority, filter_tasks_by_status


def test_priority_score():
    task = Task(name="Test", urgency=4, impact=5)
    assert task.priority_score == 20


def test_priority_score_default():
    task = Task(name="Test")
    assert task.priority_score == 9  # 3 * 3


def test_sort_by_priority():
    t1 = Task(name="Low", urgency=1, impact=1)    # score=1
    t2 = Task(name="High", urgency=5, impact=5)   # score=25
    t3 = Task(name="Mid", urgency=3, impact=3)    # score=9
    result = sort_tasks_by_priority([t1, t2, t3])
    assert result[0].name == "High"
    assert result[1].name == "Mid"
    assert result[2].name == "Low"


def test_filter_by_status():
    t1 = Task(name="A", status=TaskStatus.PENDING)
    t2 = Task(name="B", status=TaskStatus.DONE)
    t3 = Task(name="C", status=TaskStatus.PENDING)
    result = filter_tasks_by_status([t1, t2, t3], TaskStatus.PENDING)
    assert len(result) == 2
    assert all(t.status == TaskStatus.PENDING for t in result)


def test_task_status_enum():
    task = Task(name="Test", status=TaskStatus.IN_PROGRESS)
    assert task.status == TaskStatus.IN_PROGRESS


def test_task_serialization():
    task = Task(name="Serialize me", urgency=2, impact=3)
    data = task.model_dump()
    assert data["name"] == "Serialize me"
    assert data["urgency"] == 2
    assert "priority_score" in data
    assert data["priority_score"] == 6


def test_retry_strategy():
    rs = RetryStrategy(name="retry", description="try again", action="restart process")
    assert rs.name == "retry"


def test_escalation_message():
    msg = EscalationMessage(
        task_id="abc",
        task_name="My Task",
        description="failed",
        retries_attempted=3,
        strategies_tried=["strat1"],
        recommended_action="Call a human",
    )
    assert msg.task_id == "abc"
    assert msg.retries_attempted == 3
