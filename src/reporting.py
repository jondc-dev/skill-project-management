"""Status reporting for projects and jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models.project import Project
from src.models.task import TaskStatus
from src.models.job_types import RecurringJob, ContinuousJob, OneTimeProject, RunStatus


def get_status_report(project: Project) -> Dict[str, Any]:
    """
    Overall status report for a project.

    Returns
    -------
    dict with keys:
        project_id, name, phase, status, overall_progress_percent,
        tasks_by_status, blockers, risks, next_actions
    """
    tasks_by_status: Dict[str, List[str]] = {s.value: [] for s in TaskStatus}
    blockers: List[str] = []

    for task in project.tasks:
        tasks_by_status[task.status.value].append(task.name)
        if task.status in (TaskStatus.BLOCKED, TaskStatus.ESCALATED):
            blockers.append(f"{task.name} ({task.status.value})")

    # Next actions: pending tasks sorted by priority
    pending = sorted(
        [t for t in project.tasks if t.status == TaskStatus.PENDING],
        key=lambda t: t.priority_score,
        reverse=True,
    )
    next_actions = [t.name for t in pending[:3]]

    risks = [
        {
            "id": r.id,
            "description": r.description,
            "risk_score": r.risk_score,
            "status": r.status.value,
        }
        for r in project.risks
    ]

    return {
        "project_id": project.id,
        "name": project.name,
        "phase": project.phase.value,
        "status": project.status.value,
        "overall_progress_percent": project.overall_progress_percent,
        "tasks_by_status": tasks_by_status,
        "blockers": blockers,
        "risks": risks,
        "next_actions": next_actions,
    }


def get_task_summary(project: Project) -> Dict[str, List[Dict[str, Any]]]:
    """
    Tasks grouped by status, each group sorted by priority descending.

    Returns
    -------
    dict mapping status value -> list of task dicts
    """
    summary: Dict[str, List[Dict[str, Any]]] = {s.value: [] for s in TaskStatus}

    for task in sorted(project.tasks, key=lambda t: t.priority_score, reverse=True):
        summary[task.status.value].append({
            "id": task.id,
            "name": task.name,
            "priority_score": task.priority_score,
            "urgency": task.urgency,
            "impact": task.impact,
            "assigned_agent": task.assigned_agent,
        })

    return summary


def get_recurring_job_report(job: RecurringJob) -> Dict[str, Any]:
    """Status report for a recurring job."""
    completed = [r for r in job.run_history if r.status == RunStatus.SUCCESS]
    failed = [r for r in job.run_history if r.status == RunStatus.FAILED]

    durations = []
    for r in job.run_history:
        if r.completed_at and r.started_at:
            durations.append((r.completed_at - r.started_at).total_seconds())

    avg_duration = sum(durations) / len(durations) if durations else None
    success_rate = len(completed) / len(job.run_history) if job.run_history else None

    return {
        "job_id": job.id,
        "name": job.name,
        "job_type": job.job_type.value,
        "is_paused": job.is_paused,
        "total_runs": len(job.run_history),
        "successful_runs": len(completed),
        "failed_runs": len(failed),
        "success_rate": round(success_rate * 100, 1) if success_rate is not None else None,
        "avg_duration_seconds": round(avg_duration, 1) if avg_duration is not None else None,
        "next_scheduled_run": job.next_run_at.isoformat() if job.next_run_at else None,
    }


def get_continuous_job_report(job: ContinuousJob) -> Dict[str, Any]:
    """Status report for a continuous job."""
    return {
        "job_id": job.id,
        "name": job.name,
        "job_type": job.job_type.value,
        "is_paused": job.is_paused,
        "health_status": job.health_status,
        "uptime_seconds": job.uptime_seconds,
        "last_health_check": job.last_health_check.isoformat() if job.last_health_check else None,
        "health_check_interval": job.health_check_interval,
    }


def get_one_time_project_report(job: OneTimeProject, project: Optional[Project] = None) -> Dict[str, Any]:
    """Status report for a one-time project."""
    deadline_proximity = None
    if job.deadline:
        now = datetime.now(timezone.utc)
        delta = job.deadline - now
        deadline_proximity = f"{delta.days} days remaining" if delta.days >= 0 else "OVERDUE"

    report: Dict[str, Any] = {
        "job_id": job.id,
        "name": job.name,
        "job_type": job.job_type.value,
        "deadline": job.deadline.isoformat() if job.deadline else None,
        "deadline_proximity": deadline_proximity,
    }

    if project:
        report["overall_progress_percent"] = project.overall_progress_percent

    return report
