"""Priority engine: selects the next task to execute."""

from __future__ import annotations

from ..models.task import Task, TaskStatus


def get_next_task(tasks: list[Task], completed_ids: set[str]) -> Task | None:
    """Return the highest-priority eligible task.

    A task is eligible when:
    - Its status is PENDING or RETRYING.
    - All its dependency IDs are present in ``completed_ids``.

    Args:
        tasks: Full list of tasks in the project.
        completed_ids: Set of task IDs whose status is DONE.

    Returns:
        The eligible task with the highest priority_score, or None if
        no eligible task exists.
    """
    eligible = [
        t
        for t in tasks
        if t.status in (TaskStatus.PENDING, TaskStatus.RETRYING)
        and all(dep in completed_ids for dep in t.dependencies)
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda t: t.priority_score)
