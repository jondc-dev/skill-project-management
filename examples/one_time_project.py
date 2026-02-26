"""Example: One-time project with deadline."""
from datetime import datetime, timezone, timedelta
from src.skill import ProjectManagementSkill
from src.models.task import Task


def main():
    skill = ProjectManagementSkill(persistence_dir="/tmp/pm_demo")

    project = skill.create_project(
        name="Launch Website",
        description="Build and launch the company website",
        goal="Go live by end of Q1",
        success_criteria=["Website is accessible", "All pages load under 3s"],
        deadline=datetime.now(timezone.utc) + timedelta(days=30),
    )

    skill.add_task(project, "Design mockups", urgency=4, impact=5)
    skill.add_task(project, "Implement frontend", urgency=3, impact=5)
    skill.add_task(project, "Set up backend", urgency=4, impact=4)
    skill.add_task(project, "Write tests", urgency=2, impact=3)

    skill.add_risk(project, "Design delays", probability=3, impact=4, mitigation_strategy="Use template")

    def executor(task: Task) -> bool:
        print(f"  Executing: {task.name} (priority={task.priority_score})")
        return True

    print("Running project...")
    skill.run(project, executor, base_delay=0.0)
    report = skill.status_report(project)
    print(f"\nFinal status: {report['phase']} - {report['overall_progress_percent']}% complete")


if __name__ == "__main__":
    main()
