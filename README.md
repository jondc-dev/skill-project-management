# skill-project-management

OpenClaw agent skill for structured project management. Supports one-time, recurring, and continuous job types with priority-driven task execution, retry/escalation logic, scheduling, JSON persistence, and status reporting.

## Features

- **Task model** with urgency × impact priority scoring, dependency resolution, retry limits, and alternative strategies
- **Project model** with PMBOK phases, risk register, and audit log
- **Execution loop** with exponential backoff retries, alternative strategy fallback, and escalation
- **Scheduler** for recurring and continuous jobs with missed-run policies
- **JSON persistence** – save and load project state as checkpoints
- **Status reporting** – per-job-type structured reports

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from src.skill import ProjectManagementSkill

skill = ProjectManagementSkill()
project = skill.create_project("My Project", job_type="one_time")
task = skill.add_task(project, name="Build feature", urgency=4, impact=5)
project = skill.run_project(project)
report = skill.get_report(project)
print(report)
```

## Job Types

| Type         | Description                                          |
|--------------|------------------------------------------------------|
| `one_time`   | Runs once to completion; supports deadlines          |
| `recurring`  | Runs on a schedule (daily/weekly/monthly/custom)     |
| `continuous` | Ongoing monitoring; exposes health status in reports |

## Project Structure

```
src/
├── models/          # Pydantic v2 data models
│   ├── task.py      # Task, TaskStatus
│   ├── project.py   # Project, ProjectPhase, Risk, AuditEntry
│   └── job_types.py # Schedule, RunHistory, RecurrencePattern
├── engine/          # Execution engine
│   ├── priority.py       # Priority-based task selection
│   ├── blocker_manager.py # Retry, escalation, decomposition
│   └── execution_loop.py  # Main execution orchestrator
├── scheduler.py     # JobScheduler for recurring jobs
├── persistence.py   # JSON save/load
├── reporting.py     # Status report generation
└── skill.py         # ProjectManagementSkill main entry point
tests/               # pytest test suite
examples/            # Runnable examples
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Examples

```bash
python examples/one_time_project.py
python examples/recurring_job.py
python examples/continuous_job.py
```