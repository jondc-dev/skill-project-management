"""Example: continuous monitoring project."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.skill import ProjectManagementSkill
from src.models.task import TaskStatus


def main():
    skill = ProjectManagementSkill()

    project = skill.create_project(
        name="Continuous API Monitor",
        description="Ongoing health monitoring for the public API",
        job_type="continuous",
    )

    t_ping = skill.add_task(
        project,
        name="Ping health endpoint",
        urgency=5,
        impact=5,
        description="HTTP GET /health — expect 200",
        definition_of_done=["Response 200", "Latency < 500ms"],
    )

    t_db = skill.add_task(
        project,
        name="Check database connectivity",
        urgency=4,
        impact=5,
        definition_of_done=["Query succeeds in < 100ms"],
    )

    t_cache = skill.add_task(
        project,
        name="Verify cache hit rate",
        urgency=3,
        impact=3,
        definition_of_done=["Hit rate >= 80%"],
    )

    print(f"Continuous project '{project.name}' created with {len(project.tasks)} monitors.")

    # Simulate a normal run (all succeed)
    project = skill.run_project(project)
    report = skill.get_report(project)
    print(f"\nAfter healthy run:")
    print(f"  Health: {report['job_type_specific']['health']}")
    print(f"  Progress: {report['overall_progress_percent']:.0f}%")

    # Simulate degraded state by manually blocking one task
    project.tasks[0].status = TaskStatus.BLOCKED
    report = skill.get_report(project)
    print(f"\nAfter simulated degradation:")
    print(f"  Health: {report['job_type_specific']['health']}")
    print(f"  Blockers: {[b['name'] for b in report['blockers']]}")
    print(f"  Tasks by status: {report['tasks_by_status']}")


if __name__ == "__main__":
    main()
