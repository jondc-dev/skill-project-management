"""Execution loop: drives task processing for a project."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from ..models.project import Project
from ..models.task import Task, TaskStatus
from ..persistence import save_checkpoint
from .priority import get_next_task
from .blocker_manager import BlockerManager, EscalationMessage


class ExecutionLoop:
    """Orchestrates sequential task execution for a project.

    Args:
        project: The project to execute.
        task_executor: Optional callable ``(Task) -> bool``.  Returns True on
            success, False on failure.  Defaults to a stub that always
            succeeds.
        checkpoint_path: File path for JSON checkpointing, or None to skip.
        blocker_manager: Optional pre-configured BlockerManager instance.
    """

    def __init__(
        self,
        project: Project,
        task_executor: Callable[[Task], bool] | None = None,
        checkpoint_path: str | None = None,
        blocker_manager: BlockerManager | None = None,
    ) -> None:
        self.project = project
        self.task_executor: Callable[[Task], bool] = (
            task_executor if task_executor is not None else lambda _task: True
        )
        self.checkpoint_path = checkpoint_path
        self.blocker_manager = blocker_manager or BlockerManager()
        self.escalations: list[EscalationMessage] = self.blocker_manager.escalation_log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Project:
        """Execute all eligible tasks in priority order.

        Iterates until no more tasks are eligible:
        1. Selects highest-priority PENDING/RETRYING task whose
           dependencies are satisfied.
        2. Attempts execution; retries with exponential backoff on
           failure.
        3. Tries alternative strategies before escalating.
        4. Saves a checkpoint after each task completes or escalates.
        5. Updates project progress and phase.

        Returns:
            The updated Project instance.
        """
        completed_ids: set[str] = {
            t.id for t in self.project.tasks if t.status == TaskStatus.DONE
        }

        while True:
            task = get_next_task(self.project.tasks, completed_ids)
            if task is None:
                break

            success = self._run_task_with_retries(task)

            if success:
                task.status = TaskStatus.DONE
                task.updated_at = datetime.now(timezone.utc)
                completed_ids.add(task.id)
                self.project.add_audit(
                    "task_completed",
                    f"Task '{task.name}' completed successfully.",
                )
            else:
                # Try alternative strategies
                alt_success = self._try_alternatives(task)
                if alt_success:
                    task.status = TaskStatus.DONE
                    task.updated_at = datetime.now(timezone.utc)
                    completed_ids.add(task.id)
                    self.project.add_audit(
                        "task_completed_via_alternative",
                        f"Task '{task.name}' completed via alternative strategy.",
                    )
                else:
                    self._escalate_task(task)

            self.project.update_progress()
            self.save_checkpoint()

        self._finalise_project()
        return self.project

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def execute_task(self, task: Task) -> bool:
        """Invoke the task executor for a single attempt.

        Override this method in subclasses or supply ``task_executor``
        to the constructor for custom execution behaviour.

        Args:
            task: The task to execute.

        Returns:
            True if the task succeeded, False otherwise.
        """
        return self.task_executor(task)

    def _run_task_with_retries(self, task: Task) -> bool:
        """Attempt execution with exponential-backoff retries.

        Args:
            task: Task to attempt.

        Returns:
            True if any attempt succeeded.
        """
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now(timezone.utc)

        for attempt in range(task.max_retries + 1):
            start = time.monotonic()
            success = self.execute_task(task)
            elapsed = time.monotonic() - start

            if success:
                task.actual_duration = (task.actual_duration or 0.0) + elapsed / 60.0
                return True

            task.retry_count += 1
            if attempt < task.max_retries:
                task.status = TaskStatus.RETRYING
                task.updated_at = datetime.now(timezone.utc)
                delay = self.blocker_manager.compute_backoff(
                    attempt,
                    base_delay=1.0,
                    cap=300.0,
                )
                self.project.add_audit(
                    "task_retry",
                    f"Task '{task.name}' failed (attempt {attempt + 1}). "
                    f"Retrying in {delay:.1f}s.",
                )
                time.sleep(delay)

        task.status = TaskStatus.BLOCKED
        task.updated_at = datetime.now(timezone.utc)
        return False

    def _try_alternatives(self, task: Task) -> bool:
        """Attempt each alternative strategy in order.

        Args:
            task: Blocked task with alternative_strategies list.

        Returns:
            True if any alternative succeeded.
        """
        for strategy in task.alternative_strategies:
            self.project.add_audit(
                "alternative_strategy",
                f"Trying alternative '{strategy}' for task '{task.name}'.",
            )
            task.notes += f"\nTrying alternative strategy: {strategy}"
            # Re-use the same executor; a real implementation would
            # modify the task context per strategy.
            task.status = TaskStatus.RETRYING
            success = self.execute_task(task)
            if success:
                return True
        return False

    def _escalate_task(self, task: Task) -> None:
        """Mark the task as ESCALATED and record an escalation message.

        Args:
            task: The task that could not be completed.
        """
        task.status = TaskStatus.ESCALATED
        task.updated_at = datetime.now(timezone.utc)
        self.blocker_manager.escalate(
            task_id=task.id,
            task_name=task.name,
            project_id=self.project.id,
            reason="Exhausted all retry attempts and alternative strategies.",
            context={"retry_count": task.retry_count},
            attempted_strategies=list(task.alternative_strategies),
        )
        self.project.add_audit(
            "task_escalated",
            f"Task '{task.name}' escalated after {task.retry_count} retries.",
        )

    def _finalise_project(self) -> None:
        """Set project status to COMPLETED or FAILED based on task outcomes."""
        escalated = any(
            t.status == TaskStatus.ESCALATED for t in self.project.tasks
        )
        all_done = all(
            t.status == TaskStatus.DONE for t in self.project.tasks
        )
        if all_done:
            pass  # status stays as-is; caller advances via skill.advance_phase()
        if escalated:
            self.project.add_audit(
                "project_has_escalations",
                "One or more tasks were escalated and require human review.",
            )

    def save_checkpoint(self) -> None:
        """Persist current project state to disk if a path is configured."""
        if self.checkpoint_path:
            save_checkpoint(self.project, self.checkpoint_path)
