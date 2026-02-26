# Project Management Skill

**Package:** `skill-project-management`
**Install:** `pip install -e /root/clawd/skill-project-management`
**Import:** `from src import ProjectManagementSkill`

## What It Does

Gives agents structured project management for multi-step jobs. Tracks tasks with priority scoring (urgency × impact), automatic retry with exponential backoff, alternative strategy fallback, escalation to humans when stuck, checkpointing to disk, and status reporting.

**Problem it solves:** An agent gets told "approve 14 reports on a web portal." Without structure, it loses track at report #6, never reports back, and the human has no idea what happened. This skill prevents that.

## When to Use It

- **Batch operations** — N similar tasks that need tracking (approve reports, process invoices, send emails)
- **Multi-step workflows** — Tasks with dependencies (deploy: build → test → push → verify)
- **Recurring jobs** — Daily/weekly/monthly repeating work
- **Anything where losing track = bad** — If you'd be embarrassed to say "I forgot where I was," use this

## Quick Start

```python
from src import ProjectManagementSkill

skill = ProjectManagementSkill()

# 1. Create a project
project = skill.create_project(
    name="Approve Q4 Reports",
    description="Approve 3 pending reports on the finance portal",
    job_type="one_time",  # or "recurring", "continuous"
)

# 2. Add tasks
for i in range(1, 4):
    skill.add_task(
        project,
        name=f"Approve report #{i}",
        urgency=4,
        impact=3,
        max_retries=2,
        definition_of_done=["Report status shows 'Approved'"],
    )

# 3. Run with a custom executor
def my_executor(task):
    """Return True on success, False on failure."""
    print(f"Executing: {task.name}")
    # ... do the actual work (click buttons, call APIs, etc.)
    return True

project = skill.run_project(
    project,
    task_executor=my_executor,
    checkpoint_path="/tmp/q4-reports.json",
)

# 4. Get a report
report = skill.get_report(project)
print(f"Progress: {report['overall_progress_percent']}%")
print(f"Blockers: {len(report['blockers'])}")
```

## API Reference

### `ProjectManagementSkill`

| Method | Description |
|--------|-------------|
| `create_project(name, description, job_type, deadline, schedule)` | Create a new project. `job_type`: `"one_time"`, `"recurring"`, `"continuous"` |
| `add_task(project, name, urgency, impact, ...)` | Add a task. `urgency` and `impact` are 1–5; priority = urgency × impact |
| `add_risk(project, description, probability, impact, mitigation)` | Track a risk. `risk_score` = probability × impact |
| `run_project(project, task_executor, checkpoint_path)` | Execute all tasks in priority order with retries and escalation |
| `get_report(project)` | Structured status report dict |
| `save(project, path)` | Save project state to JSON |
| `load(path)` | Load project state from JSON |
| `advance_phase(project)` | Move to next PMBOK phase (initiation → planning → execution → monitoring → closure) |

### Task Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Task name |
| `urgency` | int (1-5) | Time sensitivity |
| `impact` | int (1-5) | Outcome significance |
| `dependencies` | list[str] | Task IDs that must complete first |
| `max_retries` | int | Retry limit before escalation (default: 3) |
| `definition_of_done` | list[str] | Acceptance criteria |
| `assigned_agent` | str | Agent responsible |
| `alternative_strategies` | list[str] | Fallback approaches tried before escalation |

### Task Lifecycle

```
PENDING → IN_PROGRESS → DONE
                ↓
            RETRYING (up to max_retries)
                ↓
            BLOCKED → alternative strategies tried → ESCALATED
```

### Report Structure

```python
{
    "overall_progress_percent": 66.67,
    "tasks_by_status": {"pending": 0, "done": 2, "escalated": 1, ...},
    "blockers": [{"id": "...", "name": "...", "retry_count": 3}],
    "risks": [{"description": "...", "risk_score": 15}],
    "next_actions": [{"name": "...", "priority_score": 20}],
    "job_type_specific": {...}
}
```

## Persistence (Checkpointing)

Save and resume projects across sessions:

```python
# Save during/after execution
skill.save(project, "/root/clawd/checkpoints/my-project.json")

# Resume later
project = skill.load("/root/clawd/checkpoints/my-project.json")
report = skill.get_report(project)
# Continue execution if tasks remain
project = skill.run_project(project, task_executor=my_executor)
```

Pass `checkpoint_path` to `run_project()` for automatic checkpointing after each task.

## Recurring Jobs

```python
from src import ProjectManagementSkill, Schedule, RecurrencePattern, JobScheduler
from datetime import datetime, timezone

skill = ProjectManagementSkill()
scheduler = JobScheduler()

# Create a recurring project
schedule = Schedule(
    recurrence_pattern=RecurrencePattern.DAILY,
    time_of_day="09:00",
    start_date=datetime.now(timezone.utc),
)

project = skill.create_project(
    name="Daily Health Check",
    job_type="recurring",
    schedule=schedule,
)
skill.add_task(project, name="Check API status", urgency=3, impact=4)
skill.add_task(project, name="Verify backups", urgency=2, impact=5)

# Check what's due
due_jobs = scheduler.get_due_jobs([project])

# Start a new run (resets tasks to PENDING)
if due_jobs:
    project = scheduler.create_run_instance(project)
    project = skill.run_project(project, task_executor=my_executor)
```

## The Viktor Pattern

The canonical use case: an agent receives a batch task from a human, executes it with structure, and reports back.

```python
from src import ProjectManagementSkill

skill = ProjectManagementSkill()

# Human says: "Approve these 14 reports on the finance portal"
report_ids = ["RPT-001", "RPT-002", ..., "RPT-014"]

# 1. Create the project
project = skill.create_project(
    name="Approve 14 Finance Reports",
    description="Batch approve pending reports on finance.example.com",
)

# 2. Add each report as a task
for rid in report_ids:
    skill.add_task(
        project,
        name=f"Approve {rid}",
        urgency=3,
        impact=4,
        max_retries=2,
        definition_of_done=[f"{rid} status = Approved"],
        alternative_strategies=["Refresh page and retry", "Try different browser tab"],
    )

# 3. Define the actual work
def approve_report(task):
    """Navigate to report, click approve, verify status."""
    # browser.navigate(f"https://finance.example.com/reports/{task.name.split()[-1]}")
    # browser.click("Approve")
    # return browser.text_contains("Approved")
    return True  # replace with real implementation

# 4. Execute with checkpointing
project = skill.run_project(
    project,
    task_executor=approve_report,
    checkpoint_path="/tmp/finance-approval.json",
)

# 5. Report back to the human
report = skill.get_report(project)
summary = (
    f"✅ Done: {report['tasks_by_status']['done']}/14 reports approved\n"
    f"🚨 Escalated: {report['tasks_by_status']['escalated']}"
)
if report["blockers"]:
    summary += "\n\nBlockers:\n"
    for b in report["blockers"]:
        summary += f"  - {b['name']}: {b['notes']}\n"

# Send summary back to the human
print(summary)
```

**Key benefits of this pattern:**
- If the agent crashes at report #8, it resumes from the checkpoint
- Failed reports get retried automatically (with backoff)
- Alternative strategies are tried before giving up
- Stuck tasks escalate instead of silently failing
- The human gets a clear report of what worked and what didn't

## Integration Tips

1. **Always use `checkpoint_path`** — agents crash, sessions expire, context compacts. Checkpoints save you.
2. **Write real `task_executor` functions** — the default just returns True. Your executor does the actual work.
3. **Use `definition_of_done`** — verify the task actually succeeded, don't just assume.
4. **Check the report after `run_project`** — look at `blockers` and `escalated` tasks. Report them to the human.
5. **For long-running jobs**, save checkpoints and load them in new sessions rather than keeping everything in memory.
