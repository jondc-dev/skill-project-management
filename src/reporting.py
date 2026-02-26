"""Reporting: generate human-readable project status reports."""

from __future__ import annotations

from .models.project import Project
from .models.task import TaskStatus
from .engine.priority import get_next_task


def generate_status_report(project: Project) -> dict:
    """Build a structured status report for the project.

    Args:
        project: The project to report on.

    Returns:
        A dictionary with the following keys:

        - ``overall_progress_percent`` (float): 0–100.
        - ``tasks_by_status`` (dict[str, int]): Count per TaskStatus.
        - ``blockers`` (list[dict]): Blocked or escalated task summaries.
        - ``risks`` (list[dict]): Open risk summaries.
        - ``next_actions`` (list[dict]): Up to 5 next actionable tasks.
        - ``job_type_specific`` (dict): Data specific to the job type.
    """
    # Tasks by status
    tasks_by_status: dict[str, int] = {s.value: 0 for s in TaskStatus}
    for task in project.tasks:
        tasks_by_status[task.status.value] += 1

    # Blockers
    blockers = [
        {
            "id": t.id,
            "name": t.name,
            "status": t.status.value,
            "retry_count": t.retry_count,
            "notes": t.notes,
        }
        for t in project.tasks
        if t.status in (TaskStatus.BLOCKED, TaskStatus.ESCALATED)
    ]

    # Open risks
    risks = [
        {
            "id": r.id,
            "description": r.description,
            "risk_score": r.risk_score,
            "status": r.status,
            "mitigation": r.mitigation,
        }
        for r in project.risks
        if r.status == "open"
    ]

    # Next actions (up to 5)
    completed_ids = {t.id for t in project.tasks if t.status == TaskStatus.DONE}
    next_actions = []
    remaining = list(project.tasks)
    for _ in range(5):
        nxt = get_next_task(remaining, completed_ids)
        if nxt is None:
            break
        next_actions.append(
            {
                "id": nxt.id,
                "name": nxt.name,
                "priority_score": nxt.priority_score,
                "assigned_agent": nxt.assigned_agent,
            }
        )
        # Temporarily pretend it's done so we can find subsequent tasks
        completed_ids.add(nxt.id)

    # Job-type-specific data
    job_type_specific: dict = {}
    if project.job_type == "recurring":
        job_type_specific = {
            "schedule": (
                project.schedule.model_dump() if project.schedule else None
            ),
            "total_runs": len(project.run_history),
            "last_run_status": (
                project.run_history[-1].status.value if project.run_history else None
            ),
        }
    elif project.job_type == "continuous":
        job_type_specific = {
            "total_runs": len(project.run_history),
            "health": (
                "degraded"
                if any(
                    t.status in (TaskStatus.BLOCKED, TaskStatus.ESCALATED)
                    for t in project.tasks
                )
                else "healthy"
            ),
        }
    else:  # one_time
        job_type_specific = {
            "deadline": (
                project.deadline.isoformat() if project.deadline else None
            ),
            "status": project.status.value,
        }

    return {
        "overall_progress_percent": project.overall_progress_percent,
        "tasks_by_status": tasks_by_status,
        "blockers": blockers,
        "risks": risks,
        "next_actions": next_actions,
        "job_type_specific": job_type_specific,
    }
