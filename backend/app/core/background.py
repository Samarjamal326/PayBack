from __future__ import annotations

import concurrent.futures
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.models.domain import BackgroundTask, TaskStatus

logger = logging.getLogger(__name__)


class BackgroundExecutor(ABC):
    """
    Abstract interface for background execution.
    Designed to be easily replaced later (e.g., Celery, Redis queue, AWS SQS)
    without altering business logic or service callers.
    """

    @abstractmethod
    def submit(
        self,
        name: str,
        fn: Callable[..., Any],
        *args: Any,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> BackgroundTask:
        ...

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        ...


class InMemoryBackgroundExecutor(BackgroundExecutor):
    """
    Lightweight, deterministic in-memory task executor for development and test modes.
    Executes tasks using a ThreadPoolExecutor with retry policies.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, BackgroundTask] = {}
        self._idempotency_map: dict[str, str] = {}  # idempotency_key -> task_id

    def submit(
        self,
        name: str,
        fn: Callable[..., Any],
        *args: Any,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> BackgroundTask:
        # Check idempotency
        if idempotency_key and idempotency_key in self._idempotency_map:
            existing_id = self._idempotency_map[idempotency_key]
            existing_task = self._tasks.get(existing_id)
            if existing_task:
                logger.info("Idempotent task match for key '%s' (task_id=%s)", idempotency_key, existing_id)
                return existing_task.model_copy()

        task = BackgroundTask(
            name=name,
            status=TaskStatus.PENDING,
            idempotency_key=idempotency_key,
            max_retries=max_retries,
        )
        self._tasks[task.id] = task
        if idempotency_key:
            self._idempotency_map[idempotency_key] = task.id

        self._pool.submit(self._run_wrapper, task.id, fn, args, kwargs, max_retries)
        return task.model_copy()

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        item = self._tasks.get(task_id)
        return item.model_copy() if item else None

    def _run_wrapper(
        self,
        task_id: str,
        fn: Callable[..., Any],
        args: tuple,
        kwargs: dict,
        max_retries: int,
    ) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return

        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)

        attempt = 0
        while attempt <= max_retries:
            try:
                attempt += 1
                res = fn(*args, **kwargs)
                task.status = TaskStatus.COMPLETED
                task.result = str(res) if res is not None else "success"
                task.updated_at = datetime.now(timezone.utc)
                logger.info("Background task '%s' (%s) completed successfully.", task.name, task_id)
                return
            except Exception as exc:
                task.retry_count = attempt
                task.error = str(exc)
                task.updated_at = datetime.now(timezone.utc)
                if attempt <= max_retries:
                    task.status = TaskStatus.RETRYING
                    logger.warning("Background task '%s' failed (attempt %d/%d): %s. Retrying...", task.name, attempt, max_retries, exc)
                else:
                    task.status = TaskStatus.FAILED
                    logger.error("Background task '%s' permanently failed after %d retries: %s", task.name, max_retries, exc)


# Default singleton instance
_default_executor = InMemoryBackgroundExecutor()


def get_background_executor() -> BackgroundExecutor:
    return _default_executor
