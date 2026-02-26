"""Example: one-time project with task dependencies."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.skill import ProjectManagementSkill


def main():
    skill = ProjectManagementSkill()

    # Create a one-time software release project
    project = skill.create_project(
        name="v2.0 Release",
        description="Deploy version 2.0 to production",
        job_type="one_time",
    )

    # Add tasks with dependencies
    t_test = skill.add_task(
        project,
        name="Run tests",
        urgency=5,
        impact=5,
        description="Execute full test suite",
        definition_of_done=["All tests green", "Coverage >= 90%"],
    )

    t_build = skill.add_task(
        project,
        name="Build artifact",
        urgency=4,
        impact=5,
        description="Create production build",
        dependencies=[t_test.id],
        definition_of_done=["Artifact created", "Checksums verified"],
    )

    t_deploy = skill.add_task(
        project,
        name="Deploy to production",
        urgency=5,
        impact=5,
        description="Run deployment pipeline",
        dependencies=[t_build.id],
        alternative_strategies=["Blue-green swap", "Canary release"],
        definition_of_done=["Service responding", "Monitors green"],
    )

    # Add a risk
    skill.add_risk(
        project,
        description="Database migration may fail",
        probability=2,
        impact=5,
        mitigation="Backup database before migration; have rollback script ready",
    )

    print(f"Project '{project.name}' created with {len(project.tasks)} tasks.")

    # Advance through phases
    skill.advance_phase(project)  # planning
    skill.advance_phase(project)  # execution

    # Run the project
    project = skill.run_project(project)

    # Get report
    report = skill.get_report(project)
    print(f"\nProgress: {report['overall_progress_percent']:.0f}%")
    print(f"Tasks by status: {report['tasks_by_status']}")
    print(f"Blockers: {len(report['blockers'])}")
    print(f"Open risks: {len(report['risks'])}")

    if report["next_actions"]:
        print(f"Next action: {report['next_actions'][0]['name']}")
    else:
        print("All tasks complete!")


if __name__ == "__main__":
    main()
