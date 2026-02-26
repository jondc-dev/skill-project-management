"""Execution loop: drives task processing for a project."""

from __future__ import annotations

import asyncio
import inspect
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Optional

from ..models.project import Project, ProjectPhase, ProjectStatus
from ..models.task import Task, TaskStatus
from ..persistence import save_checkpoint
from .priority import get_next_task
from .blocker_manager import BlockerManager, EscalationMessage


class ExecutionLoop:
    """Orchestrates task execution for a project.

    Args:
        project: The project to execute.
        task_executor: Optional callable ``(Task) -> bool`` or
            ``(Task, strategy=None) -> bool``.  Returns True on success,
            False on failure.  Defaults to a stub that always succeeds.
        checkpoint_path: File path for JSON checkpointing, or None to skip.
        blocker_manager: Optional pre-configured BlockerManager instance.
        async_mode: When True, ``asyncio.sleep`` is used instead of
            ``time.sleep`` during retry backoff (requires running inside
            an async context via ``run_async``).
        backoff_callback: Optional ``(delay: float) -> None`` callable
            invoked instead of sleeping during retry backoff.  When
            provided it overrides both ``time.sleep`` and
            ``asyncio.sleep``.
        parallel: When True, all dependency-ready tasks are executed
            concurrently before moving to the next batch.
        max_workers: Thread-pool size when ``parallel=True`` and not in
            async mode.
    """

    def __init__(
        self,
        project: Project,
        task_executor: Callable[[Task], bool] | None = None,
        checkpoint_path: str | None = None,
        blocker_manager: BlockerManager | None = None,
        async_mode: bool = False,
        backoff_callback: Callable[[float], None] | None = None,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> None:
        self.project = project
        self.task_executor: Callable[[Task], bool] = (
            task_executor if task_executor is not None else lambda _task: True
        )
        self.checkpoint_path = checkpoint_path
        self.blocker_manager = blocker_manager or BlockerManager()
        self.escalations: list[EscalationMessage] = self.blocker_manager.escalation_log
        self.async_mode = async_mode
        self.backoff_callback = backoff_callback
        self.parallel = parallel
        self.max_workers = max_workers
        # Detect whether the executor accepts a ``strategy`` keyword arg.
        self._executor_accepts_strategy: bool = self._check_executor_strategy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Project:
        """Execute all eligible tasks in priority order (synchronous).

        Returns:
            The updated Project instance.
        """
        if self.parallel:
            return self._run_parallel()
        return self._run_sequential()

    async def run_async(self) -> Project:
        """Async version of ``run()``.  Uses ``asyncio.sleep`` for backoff.

        Returns:
            The updated Project instance.
        """
        if self.parallel:
            return await self._run_parallel_async()
        return await self._run_sequential_async()

    # ------------------------------------------------------------------
    # Sequential execution
    # ------------------------------------------------------------------

    def _run_sequential(self) -> Project:
        completed_ids: set[str] = {
            t.id for t in self.project.tasks if t.status == TaskStatus.DONE
        }

        while True:
            task = get_next_task(self.project.tasks, completed_ids)
            if task is None:
                break

            success = self._run_task_with_retries(task)
            self._handle_task_outcome(task, success, completed_ids)
            self.project.update_progress()
            self.save_checkpoint()

        self._finalise_project()
        return self.project

    async def _run_sequential_async(self) -> Project:
        completed_ids: set[str] = {
            t.id for t in self.project.tasks if t.status == TaskStatus.DONE
        }

        while True:
            task = get_next_task(self.project.tasks, completed_ids)
            if task is None:
                break

            success = await self._run_task_with_retries_async(task)
            self._handle_task_outcome(task, success, completed_ids)
            self.project.update_progress()
            self.save_checkpoint()

        self._finalise_project()
        return self.project

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    def _run_parallel(self) -> Project:
        """Execute batches of dependency-ready tasks concurrently."""
        completed_ids: set[str] = {
            t.id for t in self.project.tasks if t.status == TaskStatus.DONE
        }

        while True:
            ready = self._get_ready_batch(completed_ids)
            if not ready:
                break

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._run_task_with_retries, task): task
                    for task in ready
                }
                for future in as_completed(futures):
                    task = futures[future]
                    success = future.result()
                    self._handle_task_outcome(task, success, completed_ids)

            self.project.update_progress()
            self.save_checkpoint()

        self._finalise_project()
        return self.project

    async def _run_parallel_async(self) -> Project:
        """Async parallel: execute batches of ready tasks via asyncio.gather."""
        completed_ids: set[str] = {
            t.id for t in self.project.tasks if t.status == TaskStatus.DONE
        }

        while True:
            ready = self._get_ready_batch(completed_ids)
            if not ready:
                break

            results = await asyncio.gather(
                *[self._run_task_with_retries_async(task) for task in ready]
            )
            for task, success in zip(ready, results):
                self._handle_task_outcome(task, success, completed_ids)

            self.project.update_progress()
            self.save_checkpoint()

        self._finalise_project()
        return self.project

    def _get_ready_batch(self, completed_ids: set[str]) -> list[Task]:
        """Return all tasks whose dependencies are currently satisfied."""
        return [
            t
            for t in self.project.tasks
            if t.status in (TaskStatus.PENDING, TaskStatus.RETRYING)
            and all(dep in completed_ids for dep in t.dependencies)
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_task_outcome(
        self, task: Task, success: bool, completed_ids: set[str]
    ) -> None:
        if success:
            task.status = TaskStatus.DONE
            task.updated_at = datetime.now(timezone.utc)
            completed_ids.add(task.id)
            self.project.add_audit(
                "task_completed",
                f"Task '{task.name}' completed successfully.",
            )
        else:
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

    def execute_task(self, task: Task, strategy: Optional[str] = None) -> bool:
        """Invoke the task executor for a single attempt.

        When ``strategy`` is not None, it is passed to the executor if
        the executor's signature supports a ``strategy`` keyword argument.

        Args:
            task: The task to execute.
            strategy: Optional alternative strategy string.

        Returns:
            True if the task succeeded, False otherwise.
        """
        if strategy is not None and self._executor_accepts_strategy:
            return self.task_executor(task, strategy=strategy)
        return self.task_executor(task)

    def _check_executor_strategy(self) -> bool:
        """Return True if the executor accepts a ``strategy`` keyword arg."""
        try:
            sig = inspect.signature(self.task_executor)
            return "strategy" in sig.parameters
        except (ValueError, TypeError):
            return False

    def _run_task_with_retries(self, task: Task) -> bool:
        """Attempt execution with exponential-backoff retries (sync).

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
                self._do_backoff(delay)

        task.status = TaskStatus.BLOCKED
        task.updated_at = datetime.now(timezone.utc)
        return False

    async def _run_task_with_retries_async(self, task: Task) -> bool:
        """Attempt execution with exponential-backoff retries (async).

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
                await self._do_backoff_async(delay)

        task.status = TaskStatus.BLOCKED
        task.updated_at = datetime.now(timezone.utc)
        return False

    def _do_backoff(self, delay: float) -> None:
        """Perform sync backoff: invoke callback or sleep."""
        if self.backoff_callback is not None:
            self.backoff_callback(delay)
        else:
            time.sleep(delay)

    async def _do_backoff_async(self, delay: float) -> None:
        """Perform async backoff: invoke callback or asyncio.sleep."""
        if self.backoff_callback is not None:
            self.backoff_callback(delay)
        else:
            await asyncio.sleep(delay)

    def _try_alternatives(self, task: Task) -> bool:
        """Attempt each alternative strategy in order.

        The strategy string is passed to the executor when the executor's
        signature includes a ``strategy`` keyword argument.

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
            task.status = TaskStatus.RETRYING
            success = self.execute_task(task, strategy=strategy)
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
        """Set project status based on task outcomes and deadline."""
        # Guard: skip if already finalised to prevent duplicate audit entries
        if self.project.status in (
            ProjectStatus.COMPLETED,
            ProjectStatus.PARTIALLY_COMPLETED,
            ProjectStatus.OVERDUE,
        ):
            return

        now = datetime.now(timezone.utc)

        overdue = (
            self.project.deadline is not None
            and now > self.project.deadline
        )

        escalated = any(
            t.status == TaskStatus.ESCALATED for t in self.project.tasks
        )
        all_done = all(
            t.status == TaskStatus.DONE for t in self.project.tasks
        )

        if all_done:
            self.project.status = ProjectStatus.COMPLETED
            self.project.phase = ProjectPhase.CLOSURE
            self.project.add_audit(
                "project_completed",
                "All tasks completed successfully.",
            )
        elif escalated:
            if overdue:
                self.project.status = ProjectStatus.OVERDUE
            else:
                self.project.status = ProjectStatus.PARTIALLY_COMPLETED
            self.project.add_audit(
                "project_has_escalations",
                "One or more tasks were escalated and require human review.",
            )
        elif overdue:
            self.project.status = ProjectStatus.OVERDUE
            self.project.add_audit(
                "project_overdue",
                "Project deadline has passed.",
            )

    def save_checkpoint(self) -> None:
        """Persist current project state to disk if a path is configured."""
        if self.checkpoint_path:
            save_checkpoint(self.project, self.checkpoint_path)
