# skill-project-management

OpenClaw agent skill for structured project management. Supports one-time, recurring, and continuous job types with priority-driven task execution, retry/escalation logic, scheduling, JSON persistence, and status reporting.

## Features

- **Task model** with urgency × impact priority scoring, dependency resolution, retry limits, and alternative strategies
- **Project model** with PMBOK phases, risk register, and audit log
- **Execution loop** with exponential backoff retries, alternative strategy fallback, and escalation
- **Async execution loop** for non-blocking task execution with `asyncio`
- **Scheduler** for recurring and continuous jobs with missed-run policies
- **JSON persistence** – save and load project state as checkpoints
- **Status reporting** – per-job-type structured reports
- **OpenClaw integration** – `skill.json` manifest and `system_prompt.txt` for agent auto-discovery

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

## Async Execution

```python
import asyncio
from src.skill import ProjectManagementSkill

async def main():
    skill = ProjectManagementSkill()
    project = skill.create_project("Async Project", job_type="one_time")
    skill.add_task(project, name="Async Task", urgency=4, impact=5)
    project = await skill.async_run_project(project)
    print(skill.get_report(project))

asyncio.run(main())
```

## Job Types

| Type         | Description                                          |
|--------------|------------------------------------------------------|
| `one_time`   | Runs once to completion; supports deadlines          |
| `recurring`  | Runs on a schedule (daily/weekly/monthly/custom)     |
| `continuous` | Ongoing monitoring; exposes health status in reports |

## OpenClaw Integration

This skill ships with full OpenClaw agent auto-discovery support.

### Skill Manifest (`skill.json`)

The `skill.json` file at the repository root is the OpenClaw skill manifest. The agent runtime scans this file to automatically discover and register the skill. It declares:

- **Entry point** (`src.skill:ProjectManagementSkill`) so the runtime can import the class
- **Capabilities** listing every callable method on the skill
- **Triggers** (intent-match, keyword-match, context-match) telling the agent when to invoke the skill automatically
- **System prompt** injected into the agent context to guide proactive use

### System Prompt (`system_prompt.txt`)

`system_prompt.txt` provides rich instructions telling the agent *when* and *how* to use this skill proactively. The agent runtime injects this content into the system prompt automatically when the skill is registered.

Key behaviours it encodes:

- **Auto-detection**: invoke the skill whenever the user mentions projects, tasks, milestones, deadlines, schedules, risks, or any work-management concept
- **Proactive creation**: automatically create a project and add tasks from the user's message without waiting to be asked
- **Report surfacing**: auto-generate status reports when progress is discussed
- **Recurring job setup**: suggest and configure schedules when recurring work is mentioned

### Auto-Discovery Flow

1. Agent runtime scans the registered skill directories for `skill.json` files
2. On finding this manifest it imports `ProjectManagementSkill` and registers it under the name `"project-management"`
3. On every user turn the runtime checks the configured triggers:
   - `intent_match` – NLU-detected intents (e.g. `manage_project`, `plan_tasks`)
   - `keyword_match` – presence of keywords such as "task", "deadline", "sprint"
   - `context_match` – proactive conditions like `user_has_active_projects`
4. When any trigger fires the agent automatically invokes the appropriate skill method and presents the result

## Project Structure

```
skill.json           # OpenClaw skill manifest (auto-discovery)
system_prompt.txt    # Agent system prompt for proactive use
src/
├── models/          # Pydantic v2 data models
│   ├── task.py      # Task, TaskStatus
│   ├── project.py   # Project, ProjectPhase, Risk, AuditEntry
│   └── job_types.py # Schedule, RunHistory, RecurrencePattern
├── engine/          # Execution engine
│   ├── priority.py             # Priority-based task selection
│   ├── blocker_manager.py      # Retry, escalation, decomposition
│   ├── execution_loop.py       # Main execution orchestrator
│   └── async_execution_loop.py # Async execution orchestrator
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