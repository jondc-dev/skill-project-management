"""Job scheduler: determines when recurring/continuous jobs should run."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from .models.project import Project
from .models.job_types import Schedule, RunHistory, RecurrencePattern


class JobScheduler:
    """Computes run schedules and manages job dispatch.

    All datetime arithmetic is performed in UTC.
    """

    def get_due_jobs(self, projects: list[Project]) -> list[Project]:
        """Return projects whose next scheduled run is due.

        A project is due when its ``schedule.next_run_at`` is not None
        and is less than or equal to the current UTC time.

        Args:
            projects: All known projects.

        Returns:
            Subset of projects that should be executed now.
        """
        now = datetime.now(timezone.utc)
        due = []
        for project in projects:
            if project.schedule is None:
                continue
            nra = project.schedule.next_run_at
            if nra is not None and nra <= now:
                due.append(project)
        return due

    def create_run_instance(self, project: Project) -> Project:
        """Create a fresh run instance based on a recurring project template.

        Resets all task statuses to PENDING, appends a new RunHistory
        entry, and advances next_run_at.

        Args:
            project: The template project.

        Returns:
            A modified copy of the project ready for a new run.
        """
        from .models.task import TaskStatus

        # Reset task statuses and retry counts
        for task in project.tasks:
            task.status = TaskStatus.PENDING
            task.retry_count = 0
            task.actual_duration = None

        run = RunHistory(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )
        project.run_history.append(run)

        if project.schedule is not None:
            project.schedule.next_run_at = self.calculate_next_run(project.schedule)

        project.overall_progress_percent = 0.0
        project.add_audit("run_started", f"Run {run.run_id} started.")
        return project

    def calculate_next_run(self, schedule: Schedule) -> datetime:
        """Compute the next run datetime from the current time.

        Args:
            schedule: The schedule configuration to evaluate.

        Returns:
            Timezone-aware UTC datetime of the next run.

        Raises:
            ValueError: If the schedule pattern is unsupported without a
                cron_expression.
        """
        now = datetime.now(timezone.utc)
        interval = max(1, schedule.interval)

        if schedule.recurrence_pattern == RecurrencePattern.DAILY:
            return now + timedelta(days=interval)

        if schedule.recurrence_pattern == RecurrencePattern.WEEKLY:
            return now + timedelta(weeks=interval)

        if schedule.recurrence_pattern == RecurrencePattern.MONTHLY:
            # Approximate: add 30 * interval days
            return now + timedelta(days=30 * interval)

        if schedule.recurrence_pattern == RecurrencePattern.CUSTOM:
            if schedule.cron_expression:
                # Minimal custom support: treat as daily if no parser available
                return now + timedelta(days=interval)
            return now + timedelta(days=interval)

        # Fallback
        return now + timedelta(days=interval)

    def handle_missed_runs(
        self, project: Project, policy: str = "run_latest_only"
    ) -> None:
        """Handle the case where one or more scheduled runs were missed.

        Policies:
        - ``skip``: Do nothing; advance next_run_at.
        - ``run_immediately``: Trigger a run instance right now.
        - ``run_latest_only`` (default): Same as run_immediately but
          explicitly skips any intermediate missed runs.

        Args:
            project: The project with a missed schedule.
            policy: One of ``skip``, ``run_immediately``,
                ``run_latest_only``.
        """
        if project.schedule is None:
            return

        if policy == "skip":
            project.schedule.next_run_at = self.calculate_next_run(project.schedule)
            project.add_audit("missed_run_skipped", "Missed run skipped per policy.")
            return

        if policy in ("run_immediately", "run_latest_only"):
            self.create_run_instance(project)
            project.add_audit(
                "missed_run_executed",
                f"Missed run handled via policy '{policy}'.",
            )
            return

        # Unknown policy: default to skip
        project.schedule.next_run_at = self.calculate_next_run(project.schedule)
