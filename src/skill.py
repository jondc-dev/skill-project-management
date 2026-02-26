"""Main entry point for the project management skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from .models.project import Project, ProjectPhase, ProjectStatus, Risk
from .models.task import Task, TaskStatus
from .models.job_types import Schedule
from .engine.execution_loop import ExecutionLoop
from .persistence import save_checkpoint, load_checkpoint
from .reporting import generate_status_report

# Ordered phase progression
_PHASE_ORDER: list[ProjectPhase] = [
    ProjectPhase.INITIATION,
    ProjectPhase.PLANNING,
    ProjectPhase.EXECUTION,
    ProjectPhase.MONITORING,
    ProjectPhase.CLOSURE,
]


class ProjectManagementSkill:
    """Main entry point for the OpenClaw project management skill.

    Provides a high-level API for creating and driving projects through
    their lifecycle, regardless of job type.
    """

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str = "",
        job_type: str = "one_time",
        deadline: datetime | None = None,
        schedule: Schedule | None = None,
    ) -> Project:
        """Create and return a new Project.

        Args:
            name: Human-readable project name.
            description: Project scope and purpose.
            job_type: One of ``one_time``, ``recurring``, ``continuous``.
            deadline: Optional hard deadline (timezone-aware).
            schedule: Recurrence schedule for recurring/continuous jobs.

        Returns:
            A freshly initialised Project.
        """
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            job_type=job_type,
            deadline=deadline,
            schedule=schedule,
        )
        project.add_audit("project_created", f"Project '{name}' created.")
        return project

    def add_task(
        self,
        project: Project,
        name: str,
        urgency: int,
        impact: int,
        description: str = "",
        dependencies: list[str] | None = None,
        max_retries: int = 3,
        estimated_duration: float | None = None,
        definition_of_done: list[str] | None = None,
        assigned_agent: str | None = None,
        alternative_strategies: list[str] | None = None,
    ) -> Task:
        """Add a new task to a project.

        Args:
            project: Target project.
            name: Task name.
            urgency: Time-sensitivity score (1–5).
            impact: Outcome significance score (1–5).
            description: Detailed description.
            dependencies: IDs of prerequisite tasks.
            max_retries: Retry limit before escalation.
            estimated_duration: Expected minutes to complete.
            definition_of_done: Acceptance criteria.
            assigned_agent: Agent responsible for this task.
            alternative_strategies: Fallback approaches.

        Returns:
            The created Task (also appended to project.tasks).
        """
        task = Task(
            name=name,
            urgency=urgency,
            impact=impact,
            description=description,
            dependencies=dependencies or [],
            max_retries=max_retries,
            estimated_duration=estimated_duration,
            definition_of_done=definition_of_done or [],
            assigned_agent=assigned_agent,
            alternative_strategies=alternative_strategies or [],
        )
        project.tasks.append(task)
        project.add_audit("task_added", f"Task '{name}' added to project.")
        return task

    def add_risk(
        self,
        project: Project,
        description: str,
        probability: int,
        impact: int,
        mitigation: str = "",
    ) -> Risk:
        """Add a risk to a project.

        Args:
            project: Target project.
            description: What could go wrong.
            probability: Likelihood (1–5).
            impact: Effect magnitude (1–5).
            mitigation: Planned response.

        Returns:
            The created Risk (also appended to project.risks).
        """
        risk = Risk(
            description=description,
            probability=probability,
            impact=impact,
            mitigation=mitigation,
        )
        project.risks.append(risk)
        project.add_audit("risk_added", f"Risk '{description[:50]}' added.")
        return risk

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_project(
        self,
        project: Project,
        task_executor: Callable[[Task], bool] | None = None,
        checkpoint_path: str | None = None,
        async_mode: bool = False,
        backoff_callback: Callable[[float], None] | None = None,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> Project:
        """Execute the project via the execution loop.

        Args:
            project: The project to run.
            task_executor: Optional ``(Task) -> bool`` or
                ``(Task, strategy=None) -> bool`` callable.
                Defaults to always returning True (simulated success).
            checkpoint_path: Optional path for JSON checkpointing.
            async_mode: When True, use ``asyncio.sleep`` for retry
                backoff instead of ``time.sleep``.  Call
                ``run_project_async`` for a fully async entry point.
            backoff_callback: Optional ``(delay: float) -> None``
                callable invoked during retry backoff.  Overrides both
                ``time.sleep`` and ``asyncio.sleep`` when provided.
            parallel: When True, execute dependency-ready tasks
                concurrently within each batch.
            max_workers: Thread-pool size for parallel sync execution
                (default 4).

        Returns:
            The updated Project after execution.
        """
        loop = ExecutionLoop(
            project=project,
            task_executor=task_executor,
            checkpoint_path=checkpoint_path,
            async_mode=async_mode,
            backoff_callback=backoff_callback,
            parallel=parallel,
            max_workers=max_workers,
        )
        return loop.run()

    # ------------------------------------------------------------------
    # Reporting & persistence
    # ------------------------------------------------------------------

    def get_report(self, project: Project) -> dict:
        """Return a structured status report dict.

        Args:
            project: The project to report on.

        Returns:
            Status report dictionary (see ``reporting.generate_status_report``).
        """
        return generate_status_report(project)

    def save(self, project: Project, path: str) -> None:
        """Persist the project to a JSON file.

        Args:
            project: Project to save.
            path: Destination file path.
        """
        save_checkpoint(project, path)

    def load(self, path: str) -> Project:
        """Load a project from a JSON file.

        Args:
            path: Source file path.

        Returns:
            Reconstructed Project instance.
        """
        return load_checkpoint(path)

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def advance_phase(self, project: Project) -> Project:
        """Advance the project to the next PMBOK phase.

        Has no effect if the project is already in the CLOSURE phase.
        When advancing to CLOSURE and all tasks are done, the project
        status is automatically set to COMPLETED.

        Args:
            project: The project to advance.

        Returns:
            The same project with an updated phase.
        """
        current_index = _PHASE_ORDER.index(project.phase)
        if current_index < len(_PHASE_ORDER) - 1:
            old_phase = project.phase
            project.phase = _PHASE_ORDER[current_index + 1]
            project.add_audit(
                "phase_advanced",
                f"Phase changed from {old_phase.value} to {project.phase.value}.",
            )
            if project.phase == ProjectPhase.CLOSURE:
                all_done = all(
                    t.status.value == "done" for t in project.tasks
                )
                if all_done:
                    project.status = ProjectStatus.COMPLETED
                    project.add_audit(
                        "project_completed",
                        "All tasks done; project marked COMPLETED on closure.",
                    )
        return project
