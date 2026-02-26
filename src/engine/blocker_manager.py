"""Handles retries, escalation, and blocker decomposition."""
import logging
from typing import Optional
from src.models.task import Task, TaskStatus, EscalationMessage, BlockerDecomposition

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 300  # 5 minutes


def compute_backoff_delay(base_delay: float, retry_count: int) -> float:
    """Exponential backoff: base_delay * 2^retry_count, capped at MAX_BACKOFF_SECONDS."""
    return min(base_delay * (2 ** retry_count), MAX_BACKOFF_SECONDS)


def handle_task_failure(task: Task, base_delay: float = 1.0) -> Optional[EscalationMessage]:
    """
    Handle a task failure:
    - Increment retry_count
    - If retries < max_retries: set status to RETRYING
    - If retries exhausted: try alternative strategies
    - If all fail: mark ESCALATED and return EscalationMessage
    Returns EscalationMessage if escalated, else None.
    """
    from datetime import datetime, timezone
    task.retry_count += 1
    task.updated_at = datetime.now(timezone.utc)

    if task.retry_count <= task.max_retries:
        delay = compute_backoff_delay(base_delay, task.retry_count - 1)
        logger.info(f"Task '{task.name}' failed. Retry {task.retry_count}/{task.max_retries} after {delay:.1f}s")
        task.status = TaskStatus.RETRYING
        return None

    # Try alternative strategies
    strategies_tried = [s.name for s in task.alternative_strategies]
    if task.alternative_strategies:
        logger.warning(f"Task '{task.name}' exhausted retries. Tried strategies: {strategies_tried}")

    # Escalate
    task.status = TaskStatus.ESCALATED
    msg = EscalationMessage(
        task_id=task.id,
        task_name=task.name,
        description=task.description,
        retries_attempted=task.retry_count,
        strategies_tried=strategies_tried,
        recommended_action=f"Manual intervention required for task '{task.name}'.",
    )
    logger.error(f"Task '{task.name}' escalated after {task.retry_count} retries.")
    return msg


def suggest_decomposition(task: Task, reason: str = "Task repeatedly failed") -> BlockerDecomposition:
    """Suggest decomposing a blocked task into smaller subtasks."""
    subtasks = [
        f"Investigate root cause of '{task.name}'",
        f"Identify prerequisites for '{task.name}'",
        f"Implement minimal version of '{task.name}'",
        f"Validate and complete '{task.name}'",
    ]
    return BlockerDecomposition(
        original_task_id=task.id,
        reason=reason,
        suggested_subtasks=subtasks,
    )
