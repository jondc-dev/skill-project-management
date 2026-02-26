"""Example: Continuous monitoring job."""
from src.models.job_types import ContinuousJob
from src.scheduler import JobScheduler
from src.reporting import get_continuous_job_report


def main():
    scheduler = JobScheduler()

    job = ContinuousJob(
        name="System Health Monitor",
        description="Continuously monitors system health metrics",
        health_check_interval=60,
    )
    scheduler.add_job(job)

    # Simulate starting and health check
    due = scheduler.get_due_jobs()
    for j in due:
        print(f"Starting continuous job: {j.name}")
        run = scheduler.create_run_instance(j)
        j.health_status = "healthy"

    report = get_continuous_job_report(job)
    print(f"\nJob Report: {report}")
    print(f"Uptime: {report['uptime_seconds']:.2f}s")


if __name__ == "__main__":
    main()
