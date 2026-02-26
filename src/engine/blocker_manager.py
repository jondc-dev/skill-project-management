"""Blocker management: retry strategies, escalation, and decomposition."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class RetryStrategy(BaseModel):
    """Defines how a failed task should be retried.

    Attributes:
        strategy_name: Identifier for this strategy.
        description: Human-readable explanation.
        max_attempts: Maximum retry attempts.
        base_delay: Initial delay in seconds (for exponential backoff).
        cap: Maximum delay ceiling in seconds.
    """

    strategy_name: str
    description: str
    max_attempts: int = 3
    base_delay: float = 1.0
    cap: float = 300.0


class EscalationMessage(BaseModel):
    """Payload sent when a task cannot be resolved automatically.

    Attributes:
        task_id: ID of the blocked task.
        task_name: Human-readable task name.
        project_id: Owning project ID.
        reason: Why escalation is needed.
        context: Arbitrary key/value metadata.
        timestamp: When escalation was triggered (timezone-aware).
        attempted_strategies: Names of strategies already tried.
    """

    task_id: str
    task_name: str
    project_id: str
    reason: str
    context: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attempted_strategies: list[str] = Field(default_factory=list)


class BlockerDecomposition(BaseModel):
    """Suggested breakdown when a task is blocked.

    Attributes:
        original_task_id: The task that was blocked.
        blocker_description: What is causing the block.
        sub_tasks: Suggested sub-task names to unblock it.
        recommended_action: Single recommended next step.
    """

    original_task_id: str
    blocker_description: str
    sub_tasks: list[str] = Field(default_factory=list)
    recommended_action: str = ""


class BlockerManager:
    """Handles retry logic, alternative strategies, and escalation.

    Args:
        escalation_log: Mutable list that receives EscalationMessage objects.
    """

    def __init__(self, escalation_log: list[EscalationMessage] | None = None) -> None:
        self.escalation_log: list[EscalationMessage] = (
            escalation_log if escalation_log is not None else []
        )

    def compute_backoff(self, attempt: int, base_delay: float, cap: float) -> float:
        """Return exponential backoff delay capped at ``cap`` seconds.

        Args:
            attempt: Zero-based attempt index.
            base_delay: Starting delay in seconds.
            cap: Maximum delay ceiling.

        Returns:
            Delay in seconds.
        """
        delay = base_delay * (2**attempt)
        return min(delay, cap)

    def escalate(
        self,
        task_id: str,
        task_name: str,
        project_id: str,
        reason: str,
        context: dict | None = None,
        attempted_strategies: list[str] | None = None,
    ) -> EscalationMessage:
        """Create an EscalationMessage and record it in the log.

        Args:
            task_id: ID of the task requiring escalation.
            task_name: Name of the task.
            project_id: ID of the owning project.
            reason: Why human intervention is needed.
            context: Optional extra metadata dict.
            attempted_strategies: Strategies already tried.

        Returns:
            The created EscalationMessage.
        """
        msg = EscalationMessage(
            task_id=task_id,
            task_name=task_name,
            project_id=project_id,
            reason=reason,
            context=context or {},
            attempted_strategies=attempted_strategies or [],
        )
        self.escalation_log.append(msg)
        return msg
