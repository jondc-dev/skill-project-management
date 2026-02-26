"""Example: recurring weekly project."""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.skill import ProjectManagementSkill
from src.models.job_types import Schedule, RecurrencePattern
from src.scheduler import JobScheduler


def main():
    skill = ProjectManagementSkill()
    scheduler = JobScheduler()

    # Build a weekly schedule starting now
    schedule = Schedule(
        recurrence_pattern=RecurrencePattern.WEEKLY,
        days_of_week=[0],  # Monday
        time_of_day="09:00",
        interval=1,
        start_date=datetime.now(timezone.utc),
        next_run_at=datetime.now(timezone.utc),  # due immediately for demo
        timezone="UTC",
    )

    project = skill.create_project(
        name="Weekly Health Check",
        description="Automated weekly infrastructure health checks",
        job_type="recurring",
        schedule=schedule,
    )

    skill.add_task(project, name="Check disk usage", urgency=3, impact=4)
    skill.add_task(project, name="Check memory usage", urgency=3, impact=4)
    skill.add_task(project, name="Verify backups", urgency=4, impact=5)
    skill.add_task(project, name="Send report email", urgency=2, impact=3)

    print(f"Recurring project '{project.name}' created.")
    print(f"Schedule: {schedule.recurrence_pattern.value} every {schedule.interval} week(s)")
    print(f"Next run: {schedule.next_run_at.isoformat()}")

    # Check which jobs are due
    due = scheduler.get_due_jobs([project])
    print(f"\nDue jobs: {len(due)}")

    if due:
        # Create a run instance (resets tasks and advances schedule)
        scheduler.create_run_instance(project)
        print(f"Run instance created. Total runs: {len(project.run_history)}")
        print(f"Next run advanced to: {project.schedule.next_run_at.isoformat()}")

        # Execute the run
        project = skill.run_project(project)
        report = skill.get_report(project)
        print(f"\nRun complete. Progress: {report['overall_progress_percent']:.0f}%")
        print(f"Tasks by status: {report['tasks_by_status']}")
        print(f"Recurring info: {report['job_type_specific']}")


if __name__ == "__main__":
    main()
