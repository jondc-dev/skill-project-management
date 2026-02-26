"""
Top-level Skill interface — the public API for the project management skill.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from src.models.project import Project, ProjectStatus, Risk
from src.models.task import Task, TaskStatus
from src.models.job_types import (
    OneTimeProject, RecurringJob, ContinuousJob
)
from src.engine.execution_loop import ExecutionLoop
from src.engine.priority import sort_tasks_by_priority, filter_tasks_by_status
from src.engine.blocker_manager import suggest_decomposition
from src.scheduler import JobScheduler
from src.persistence import save_project, load_project, list_saved_projects
from src.reporting import (
    get_status_report, get_task_summary,
    get_recurring_job_report, get_continuous_job_report, get_one_time_project_report
)

logger = logging.getLogger(__name__)


class ProjectManagementSkill:
    """
    The primary interface for the project management skill.

    Usage
    -----
    skill = ProjectManagementSkill(persistence_dir="./data")
    project = skill.create_project("My Project", goal="Ship v1.0")
    task = skill.add_task(project, "Design API")
    skill.run(project, task_executor=my_executor)
    """

    def __init__(self, persistence_dir: str = "./checkpoints") -> None:
        self.persistence_dir = persistence_dir
        self.scheduler = JobScheduler()

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str = "",
        goal: str = "",
        success_criteria: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        deadline: Optional[datetime] = None,
    ) -> Project:
        """Create a new project (Initiation phase)."""
        project = Project(
            name=name,
            description=description,
            goal=goal,
            success_criteria=success_criteria or [],
            constraints=constraints or [],
            deadline=deadline,
        )
        project.log_action("skill", f"Project '{name}' created.")
        save_project(project, self.persistence_dir)
        return project

    def load_project(self, project_id: str) -> Optional[Project]:
        """Load a previously saved project."""
        return load_project(project_id, self.persistence_dir)

    def list_projects(self) -> List[str]:
        """List all saved project IDs."""
        return list_saved_projects(self.persistence_dir)

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def add_task(self, project: Project, name: str, **kwargs) -> Task:
        """Add a task to a project."""
        task = Task(name=name, **kwargs)
        project.tasks.append(task)
        project.log_action("skill", f"Task '{name}' added.", {"task_id": task.id})
        save_project(project, self.persistence_dir)
        return task

    def update_task_status(self, project: Project, task_id: str, status: TaskStatus) -> Optional[Task]:
        """Update a task's status."""
        for task in project.tasks:
            if task.id == task_id:
                task.status = status
                task.updated_at = datetime.now(timezone.utc)
                project.log_action("skill", f"Task status updated to {status.value}", {"task_id": task_id})
                save_project(project, self.persistence_dir)
                return task
        return None

    def delegate_task(self, project: Project, task_id: str, agent_name: str) -> Optional[Task]:
        """Delegate a task to another agent."""
        for task in project.tasks:
            if task.id == task_id:
                task.assigned_agent = agent_name
                task.updated_at = datetime.now(timezone.utc)
                project.log_action("skill", f"Task delegated to {agent_name}", {"task_id": task_id})
                save_project(project, self.persistence_dir)
                return task
        return None

    # ------------------------------------------------------------------
    # Risk management
    # ------------------------------------------------------------------

    def add_risk(self, project: Project, description: str, probability: int, impact: int,
                 mitigation_strategy: str = "") -> Risk:
        """Add a risk to the project risk register."""
        risk = Risk(
            description=description,
            probability=probability,
            impact=impact,
            mitigation_strategy=mitigation_strategy,
        )
        project.risks.append(risk)
        project.log_action("skill", f"Risk added: {description}")
        save_project(project, self.persistence_dir)
        return risk

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(
        self,
        project: Project,
        task_executor: Callable[[Task], bool],
        base_delay: float = 1.0,
    ) -> None:
        """
        Run the project execution loop.

        Parameters
        ----------
        project : Project
        task_executor : callable
            Called with each Task. Should return True on success, False on failure.
        base_delay : float
            Base seconds for exponential backoff.
        """
        loop = ExecutionLoop(
            project=project,
            task_executor=task_executor,
            persistence_path=self.persistence_dir,
            base_delay=base_delay,
            scheduler=self.scheduler,
        )
        loop.run()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def status_report(self, project: Project) -> dict:
        """Get overall project status report."""
        return get_status_report(project)

    def task_summary(self, project: Project) -> dict:
        """Get tasks grouped by status."""
        return get_task_summary(project)

    def decompose_blocker(self, task: Task, reason: str = "") -> dict:
        """Suggest subtasks for a blocked task."""
        return suggest_decomposition(task, reason or f"Task '{task.name}' is blocked").model_dump()

    # ------------------------------------------------------------------
    # Job scheduling
    # ------------------------------------------------------------------

    def register_recurring_job(self, job: RecurringJob) -> None:
        """Register a recurring job with the scheduler."""
        self.scheduler.add_job(job)

    def register_continuous_job(self, job: ContinuousJob) -> None:
        """Register a continuous job with the scheduler."""
        self.scheduler.add_job(job)

    def recurring_job_report(self, job: RecurringJob) -> dict:
        return get_recurring_job_report(job)

    def continuous_job_report(self, job: ContinuousJob) -> dict:
        return get_continuous_job_report(job)

    def one_time_report(self, job: OneTimeProject, project: Optional[Project] = None) -> dict:
        return get_one_time_project_report(job, project)
