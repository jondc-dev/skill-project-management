"""Priority calculation and task ordering utilities."""
from typing import List, Optional
from src.models.task import Task, TaskStatus


def calculate_priority_score(urgency: int, impact: int) -> int:
    """Calculate priority score as urgency * impact (1-25 scale)."""
    return urgency * impact


def sort_tasks_by_priority(tasks: List[Task]) -> List[Task]:
    """Return tasks sorted by priority_score descending."""
    return sorted(tasks, key=lambda t: t.priority_score, reverse=True)


def filter_tasks_by_status(tasks: List[Task], status: TaskStatus) -> List[Task]:
    """Return tasks matching the given status."""
    return [t for t in tasks if t.status == status]


def get_next_task(tasks: List[Task], completed_ids: set) -> Optional[Task]:
    """
    Get the highest-priority pending task whose dependencies are all met.
    completed_ids: set of task IDs that are done.
    """
    eligible = [
        t for t in tasks
        if t.status == TaskStatus.PENDING
        and all(dep in completed_ids for dep in t.dependencies)
    ]
    if not eligible:
        return None
    return sort_tasks_by_priority(eligible)[0]
