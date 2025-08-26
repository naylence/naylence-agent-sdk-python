import asyncio
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, AsyncIterator, Optional

from naylence.fame.util.logging import getLogger

from naylence.agent.a2a_types import (
    Artifact,
    Message,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskQueryParams,
    TaskSendParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from naylence.agent.base_agent import TERMINAL_TASK_STATES, BaseAgent
from naylence.agent.util import make_message

logger = getLogger(__name__)

# sentinel for end-of-stream
_end_of_stream_sentinel = TaskStatusUpdateEvent(
    id="_sentinel", status=TaskStatus(state=TaskState.UNKNOWN)
)

_DEFAULT_EVENT_QUEUE_SIZE = 1000


class BackgroundTaskAgent(BaseAgent, ABC):
    def __init__(
        self,
        *args,
        max_queue_size: int = _DEFAULT_EVENT_QUEUE_SIZE,
        max_task_lifetime_ms: Optional[int] = None,
        completed_cache_size: int = 100,
        completed_cache_ttl_sec: float = 300.0,
    ):
        super().__init__(*args)
        self._max_queue_size = max_queue_size
        self._max_task_lifetime_sec = (
            max_task_lifetime_ms / 1000 if max_task_lifetime_ms else None
        )
        # in-flight tasks
        self._task_statuses: dict[str, TaskStatus] = {}
        self._task_event_queues: dict[
            str,
            asyncio.Queue[TaskStatusUpdateEvent | TaskArtifactUpdateEvent],
        ] = {}

        # completed-task LRU cache: id -> (status, timestamp)
        self._completed: OrderedDict[str, tuple[TaskStatus, float]] = OrderedDict()
        self._completed_cache_size = completed_cache_size
        self._completed_cache_ttl = completed_cache_ttl_sec

        # guard concurrent access
        self._status_lock = asyncio.Lock()

    def _is_terminal_task_state(self, task_id: str) -> bool:
        # check in-flight
        status = self._task_statuses.get(task_id)
        if status and status.state in TERMINAL_TASK_STATES:
            return True
        # check completed cache
        return task_id in self._completed

    async def start_task(self, params: TaskSendParams) -> Task:
        self._task_event_queues[params.id] = asyncio.Queue(maxsize=self._max_queue_size)
        await self.update_task_state(params.id, TaskState.WORKING)

        # background runner
        asyncio.create_task(self._run_background_task(params))

        # enforce max task lifetime
        if self._max_task_lifetime_sec:
            asyncio.create_task(self._enforce_max_lifetime(params.id))

        return await self.get_task_status(TaskQueryParams(id=params.id))

    async def _enforce_max_lifetime(self, task_id: str) -> None:
        assert self._max_task_lifetime_sec
        await asyncio.sleep(self._max_task_lifetime_sec)
        # only cancel if still not terminal
        if not self._is_terminal_task_state(task_id):
            await self.update_task_state(task_id, TaskState.CANCELED)
        # signal end-of-stream
        # queue = self._task_event_queues.pop(task_id, None)
        # if queue:
        #     queue.put_nowait(_end_of_stream_sentinel)
        queue = self._task_event_queues.get(task_id)
        if queue:
            await queue.put(_end_of_stream_sentinel)

    async def _run_background_task(self, params: TaskSendParams) -> None:
        try:
            result = await self.run_background_task(params)
        except Exception as e:
            err_msg = make_message(str(e))
            await self.update_task_state(params.id, TaskState.FAILED, err_msg)
            logger.exception(f"Background task {params.id} failed: {e}")
        else:
            await self.update_task_state(
                params.id, TaskState.COMPLETED, make_message(result)
            )
        finally:
            # signal end-of-stream once; leave the queue in place so that anyone
            # who subscribes *after* completion still sees the final status
            queue = self._task_event_queues.get(params.id)
            if queue:
                await queue.put(_end_of_stream_sentinel)

    @abstractmethod
    async def run_background_task(self, params: TaskSendParams) -> Any: ...

    async def get_task_state(self, task_id: str) -> TaskState:
        task_status = await self.get_task_status(TaskQueryParams(id=task_id))
        return task_status.status.state if task_status else TaskState.UNKNOWN

    async def get_task_status(self, params: TaskQueryParams) -> Task:
        async with self._status_lock:
            # check active
            status = self._task_statuses.get(params.id)
            if status:
                return Task(id=params.id, status=status)
            # check completed cache
            entry = self._completed.get(params.id)
            if entry:
                status, ts = entry
                if time.monotonic() - ts <= self._completed_cache_ttl:
                    return Task(id=params.id, status=status)
                # expired
                self._completed.pop(params.id, None)
        raise ValueError(f"Unknown or expired task {params.id}")

    async def update_task_state(
        self, task_id: str, state: TaskState, message: Optional[Message] = None
    ) -> bool:
        async with self._status_lock:
            # no updates once terminal
            if self._is_terminal_task_state(task_id):
                return False

            self._task_statuses[task_id] = TaskStatus(state=state, message=message)
            queue = self._task_event_queues.get(task_id)
            if not queue:
                logger.warning(f"Cannot update state for task_id {task_id}")
                return False

            await queue.put(
                TaskStatusUpdateEvent(id=task_id, status=self._task_statuses[task_id])
            )

            if state in TERMINAL_TASK_STATES:
                # move to completed cache
                final = self._task_statuses.pop(task_id)
                if len(self._completed) >= self._completed_cache_size:
                    self._completed.popitem(last=False)
                self._completed[task_id] = (final, time.monotonic())

                # ── ② schedule TTL purge of cache *and* queue ───────────────
                asyncio.create_task(self._purge_completed_after_ttl(task_id))

            return True

    async def update_task_artifact(self, task_id: str, artifact: Artifact):
        queue = self._task_event_queues.get(task_id)
        if not queue:
            logger.warning(f"Cannot update artifact for task_id {task_id}")
            return
        await queue.put(TaskArtifactUpdateEvent(id=task_id, artifact=artifact))

    async def subscribe_to_task_updates(
        self, params: TaskSendParams
    ) -> AsyncIterator[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]:
        async def _stream() -> AsyncIterator[
            TaskStatusUpdateEvent | TaskArtifactUpdateEvent
        ]:
            queue = self._task_event_queues.get(params.id)
            # ── ① late subscription: task already finished ───────────────────
            if not queue:
                entry = self._completed.get(params.id)
                if entry:  # still in TTL window
                    status, _ = entry
                    yield TaskStatusUpdateEvent(id=params.id, status=status)
                return  # ← generator ends cleanly

            seen_terminal = False
            while True:
                try:
                    evt = await asyncio.wait_for(
                        queue.get(), timeout=self._max_task_lifetime_sec
                    )
                except asyncio.TimeoutError:
                    break
                if evt is _end_of_stream_sentinel:
                    break
                # dedupe multiple terminal events
                if (
                    isinstance(evt, TaskStatusUpdateEvent)
                    and evt.status.state in TERMINAL_TASK_STATES
                ):
                    if seen_terminal:
                        continue
                    seen_terminal = True
                yield evt

        return _stream()

    async def unsubscribe_task(self, params: TaskIdParams) -> Any:
        queue = self._task_event_queues.pop(params.id, None)
        if queue:
            queue.put_nowait(_end_of_stream_sentinel)

    async def cancel_task(self, params: TaskIdParams) -> Task:
        await self.update_task_state(params.id, TaskState.CANCELED)
        return await self.get_task_status(TaskQueryParams(id=params.id))

    async def _purge_completed_after_ttl(self, task_id: str) -> None:
        await asyncio.sleep(self._completed_cache_ttl)
        # drop cached status
        self._completed.pop(task_id, None)
        # drop lingering event queue (if client forgot to unsubscribe)
        self._task_event_queues.pop(task_id, None)
