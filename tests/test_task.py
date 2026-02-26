"""Tests for Task model."""

import pytest
from pydantic import ValidationError

from src.models.task import Task, TaskStatus


def make_task(**kwargs) -> Task:
    defaults = dict(name="Test Task", urgency=3, impact=3)
    defaults.update(kwargs)
    return Task(**defaults)


class TestTaskCreation:
    def test_default_status_is_pending(self):
        task = make_task()
        assert task.status == TaskStatus.PENDING

    def test_priority_score_computed(self):
        task = make_task(urgency=4, impact=5)
        assert task.priority_score == 20

    def test_priority_score_min(self):
        task = make_task(urgency=1, impact=1)
        assert task.priority_score == 1

    def test_priority_score_max(self):
        task = make_task(urgency=5, impact=5)
        assert task.priority_score == 25

    def test_id_is_generated(self):
        t1 = make_task()
        t2 = make_task()
        assert t1.id != t2.id
        assert len(t1.id) == 36  # UUID format

    def test_created_at_is_timezone_aware(self):
        task = make_task()
        assert task.created_at.tzinfo is not None

    def test_updated_at_is_timezone_aware(self):
        task = make_task()
        assert task.updated_at.tzinfo is not None

    def test_default_dependencies_empty(self):
        task = make_task()
        assert task.dependencies == []

    def test_default_definition_of_done_empty(self):
        task = make_task()
        assert task.definition_of_done == []

    def test_description_default_empty(self):
        task = make_task()
        assert task.description == ""

    def test_assigned_agent_default_none(self):
        task = make_task()
        assert task.assigned_agent is None

    def test_custom_fields(self):
        task = make_task(
            name="Deploy",
            urgency=5,
            impact=4,
            description="Deploy to prod",
            dependencies=["abc", "def"],
            max_retries=5,
            definition_of_done=["CI passes", "Smoke test passes"],
            assigned_agent="agent-007",
            alternative_strategies=["rollback", "hotfix"],
            notes="Handle with care",
        )
        assert task.name == "Deploy"
        assert task.priority_score == 20
        assert len(task.dependencies) == 2
        assert task.max_retries == 5
        assert task.assigned_agent == "agent-007"
        assert len(task.alternative_strategies) == 2


class TestTaskValidation:
    @pytest.mark.parametrize("urgency", [0, 6, -1, 100])
    def test_invalid_urgency_raises(self, urgency):
        with pytest.raises(ValidationError):
            make_task(urgency=urgency)

    @pytest.mark.parametrize("impact", [0, 6, -1, 100])
    def test_invalid_impact_raises(self, impact):
        with pytest.raises(ValidationError):
            make_task(impact=impact)

    @pytest.mark.parametrize("urgency", [1, 2, 3, 4, 5])
    def test_valid_urgency(self, urgency):
        task = make_task(urgency=urgency)
        assert task.urgency == urgency

    @pytest.mark.parametrize("impact", [1, 2, 3, 4, 5])
    def test_valid_impact(self, impact):
        task = make_task(impact=impact)
        assert task.impact == impact


class TestTaskStatusTransitions:
    def test_set_status_in_progress(self):
        task = make_task()
        task.status = TaskStatus.IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS

    def test_set_status_done(self):
        task = make_task()
        task.status = TaskStatus.DONE
        assert task.status == TaskStatus.DONE

    def test_set_status_blocked(self):
        task = make_task()
        task.status = TaskStatus.BLOCKED
        assert task.status == TaskStatus.BLOCKED

    def test_set_status_retrying(self):
        task = make_task()
        task.status = TaskStatus.RETRYING
        assert task.status == TaskStatus.RETRYING

    def test_set_status_escalated(self):
        task = make_task()
        task.status = TaskStatus.ESCALATED
        assert task.status == TaskStatus.ESCALATED

    def test_priority_score_recalculated_on_copy(self):
        task = make_task(urgency=2, impact=3)
        assert task.priority_score == 6
        updated = task.model_copy(update={"urgency": 5, "impact": 5})
        # model_copy does not re-run validators by default; score stays 6
        # unless we re-validate
        validated = Task.model_validate(updated.model_dump())
        assert validated.priority_score == 25
