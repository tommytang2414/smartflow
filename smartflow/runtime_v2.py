"""V2 parent-process adapter for recording terminated collector timeouts."""

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from smartflow.health import SourceHealthPolicy
from smartflow.outcomes import record_timeout_outcome
from smartflow.runtime import ProcessTimeoutError, run_in_process


def run_in_process_with_v2_timeout(
    callable_path: str,
    *,
    policy: SourceHealthPolicy,
    session_factory: Callable[[], Session],
    args: tuple = (),
    kwargs: dict | None = None,
    timeout_seconds: float,
) -> Any:
    """Run a child and persist timeout evidence from the surviving parent process."""
    started_at = datetime.now(timezone.utc)
    try:
        return run_in_process(
            callable_path,
            args=args,
            kwargs=kwargs,
            timeout_seconds=timeout_seconds,
        )
    except ProcessTimeoutError as error:
        finished_at = datetime.now(timezone.utc)
        with session_factory() as session:
            record_timeout_outcome(
                session,
                policy=policy,
                started_at=started_at,
                finished_at=finished_at,
                timeout_seconds=timeout_seconds,
                error=error,
            )
        raise
