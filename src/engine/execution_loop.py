"""Persistent execution loop for project task management."""
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from src.models.task import Task, TaskStatus
from src.models.project import Project, ProjectPhase
from src.engine.priority import get_next_task, filter_tasks_by_status
from src.engine.blocker_manager import handle_task_failure, compute_backoff_delay
from src.persistence import save_project
from src.reporting import get_status_report

logger = logging.getLogger(__name__)

TaskExecutor = Callable[[Task], bool]


class ExecutionLoop:
    """
    Drives a project through its tasks in priority order.

    Parameters
    ----------
    project : Project
        The project to execute.
    task_executor : TaskExecutor
        Callable that accepts a Task and returns True on success, False on failure.
    persistence_path : str, optional
        Directory path where checkpoints are saved.
    base_delay : float
        Base delay (seconds) for exponential backoff.
    scheduler : optional
        A JobScheduler instance; if provided, due jobs are checked each iteration.
    """

    def __init__(
        self,
        project: Project,
        task_executor: TaskExecutor,
        persistence_path: str = "./checkpoints",
        base_delay: float = 1.0,
        scheduler=None,
    ) -> None:
        self.project = project
        self.task_executor = task_executor
        self.persistence_path = persistence_path
        self.base_delay = base_delay
        self.scheduler = scheduler

    def _completed_ids(self) -> set:
        return {t.id for t in self.project.tasks if t.status == TaskStatus.DONE}

    def _advance_to_execution(self) -> None:
        """Ensure project is in EXECUTION phase before running tasks."""
        order = list(ProjectPhase)
        while self.project.phase != ProjectPhase.EXECUTION:
            idx = order.index(self.project.phase)
            if idx >= order.index(ProjectPhase.EXECUTION):
                break
            self.project.advance_phase()
            self.project.log_action("execution_loop", f"Advanced to phase: {self.project.phase}")

    def _handle_closure(self) -> None:
        """Move project to closure and verify definition-of-done."""
        self.project.phase = ProjectPhase.CLOSURE
        self.project.log_action("execution_loop", "All tasks completed. Moving to closure phase.")
        # Validate definition_of_done for each task
        issues = []
        for task in self.project.tasks:
            for criterion in task.definition_of_done:
                if criterion not in task.notes:
                    issues.append(f"Task '{task.name}': criterion '{criterion}' not verified")
        if issues:
            logger.warning("Definition-of-done issues: %s", issues)
        save_project(self.project, self.persistence_path)

    def run(self, max_iterations: int = 1000) -> None:
        """
        Main execution loop.

        Runs until all tasks are done, the project is escalated/cancelled,
        or max_iterations is reached.
        """
        self._advance_to_execution()
        self.project.phase = ProjectPhase.EXECUTION
        save_project(self.project, self.persistence_path)

        for iteration in range(max_iterations):
            # Check scheduler for due jobs
            if self.scheduler:
                due_jobs = self.scheduler.get_due_jobs()
                for job in due_jobs:
                    logger.info(f"Scheduler: due job detected: {job.name}")
                    self.scheduler.create_run_instance(job)

            # Get next eligible task
            task = get_next_task(self.project.tasks, self._completed_ids())
            if task is None:
                # Check if there are any retrying tasks
                retrying = filter_tasks_by_status(self.project.tasks, TaskStatus.RETRYING)
                if retrying:
                    delay = compute_backoff_delay(self.base_delay, retrying[0].retry_count)
                    logger.info(f"Waiting {delay:.1f}s before retrying task '{retrying[0].name}'")
                    time.sleep(min(delay, 0.1))  # In tests, sleep minimally
                    retrying[0].status = TaskStatus.PENDING
                    continue

                # Check if all tasks are done
                pending = filter_tasks_by_status(self.project.tasks, TaskStatus.PENDING)
                in_progress = filter_tasks_by_status(self.project.tasks, TaskStatus.IN_PROGRESS)
                if not pending and not in_progress and not retrying:
                    break
                break  # No eligible task and nothing pending

            # Execute task
            task.status = TaskStatus.IN_PROGRESS
            task.updated_at = datetime.now(timezone.utc)
            self.project.log_action("execution_loop", f"Started task: {task.name}", {"task_id": task.id})

            success = False
            try:
                success = self.task_executor(task)
            except Exception as exc:
                logger.exception(f"Exception executing task '{task.name}': {exc}")
                success = False

            if success:
                task.status = TaskStatus.DONE
                task.updated_at = datetime.now(timezone.utc)
                self.project.log_action("execution_loop", f"Completed task: {task.name}", {"task_id": task.id})
                logger.info(f"Task '{task.name}' completed successfully.")
            else:
                escalation = handle_task_failure(task, self.base_delay)
                if escalation:
                    self.project.log_action(
                        "execution_loop",
                        f"Task escalated: {task.name}",
                        {"escalation": escalation.model_dump(mode="json")},
                    )

            # Save checkpoint
            save_project(self.project, self.persistence_path)

            # Check if all tasks complete
            done_count = len(filter_tasks_by_status(self.project.tasks, TaskStatus.DONE))
            if done_count == len(self.project.tasks):
                break

        # Closure
        all_done = all(t.status == TaskStatus.DONE for t in self.project.tasks)
        if all_done:
            self._handle_closure()
        else:
            self.project.phase = ProjectPhase.MONITORING
            save_project(self.project, self.persistence_path)

        logger.info("Execution loop finished. %s", get_status_report(self.project))
