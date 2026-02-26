"""Example: Recurring job (daily report generation)."""
from datetime import datetime, timezone, timedelta
from src.models.job_types import RecurringJob, Schedule, RecurrencePattern, MissedRunPolicy
from src.scheduler import JobScheduler


def main():
    scheduler = JobScheduler()

    schedule = Schedule(
        recurrence_pattern=RecurrencePattern.DAILY,
        time_of_day="09:00",
        start_date=datetime.now(timezone.utc),
    )
    job = RecurringJob(
        name="Daily Report",
        description="Generate and send daily project status report",
        schedule=schedule,
        missed_run_policy=MissedRunPolicy.RUN_LATEST_ONLY,
    )
    job.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # Due now
    scheduler.add_job(job)

    due_jobs = scheduler.get_due_jobs()
    for j in due_jobs:
        print(f"Running due job: {j.name}")
        run = scheduler.create_run_instance(j)
        run.tasks_completed = 5
        run.summary = "Daily report sent successfully"
        print(f"  Run created. Next run at: {j.next_run_at}")

    from src.reporting import get_recurring_job_report
    report = get_recurring_job_report(job)
    print(f"\nJob Report: {report}")


if __name__ == "__main__":
    main()
