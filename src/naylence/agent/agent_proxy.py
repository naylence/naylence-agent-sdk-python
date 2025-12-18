"""Remote proxy for communicating with agents.

:class:`AgentProxy` provides a client-side interface for invoking agents
over the Fame network. Create proxies using :meth:`Agent.remote` or
:meth:`Agent.remote_by_address`.

The proxy handles JSON-RPC serialization, streaming subscriptions, and
error propagation transparently.
"""
import asyncio
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    TypeVar,
    cast,
    overload,
)

from naylence.fame.core import FameAddress, FameFabric, generate_id
from naylence.fame.service import RpcProxy

from naylence.agent.a2a_types import (
    AgentCard,
    AuthenticationInfo,
    DataPart,
    PushNotificationConfig,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskSendParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from naylence.agent.agent import Agent, TAgent
from naylence.agent.base_agent import TERMINAL_TASK_STATES
from naylence.agent.util import first_text_part, make_task_params

R = TypeVar("R")


class AgentProxy(Agent, RpcProxy, Generic[TAgent]):
    """Remote proxy for invoking agent methods over the network.

    Created via :meth:`Agent.remote` or :meth:`Agent.remote_by_address`.
    Supports both synchronous task execution (:meth:`run_task`) and
    async streaming (:meth:`subscribe_to_task_updates`).

    The proxy can target agents by:
        - Direct address (``fame://agent-name``)
        - Capability matching (finds any agent advertising the capability)
        - Natural language intent (future)

    Args:
        address: Direct Fame address of the agent.
        capabilities: List of capabilities to match.
        intent_nl: Natural language description (future).
        fabric: Fame fabric for network communication.

    Raises:
        ValueError: If not exactly one of address/capabilities/intent_nl is set.

    Example:
        >>> proxy = await MyAgent.remote(fabric)
        >>> result = await proxy.run_task({"x": 1, "y": 2})
    """

    # -- Construction ----------------------------------------------------- #
    def __init__(
        self,
        *,
        address: Optional[FameAddress] = None,
        capabilities: Optional[list[str]] = None,
        intent_nl: Optional[str] = None,
        fabric: FameFabric,
    ) -> None:
        """Create an agent proxy.

        Args:
            address: Direct Fame address of the target agent.
            capabilities: Capability list for capability-based routing.
            intent_nl: Natural language intent for semantic routing (future).
            fabric: Fame fabric instance for network calls.

        Raises:
            ValueError: If not exactly one routing method is specified.
        """
        super().__init__(address=address, capabilities=capabilities)

        chosen = sum(x is not None for x in (address, capabilities, intent_nl))
        if chosen != 1:
            raise ValueError(
                "Provide exactly one of address | capabilities | intent_nl"
            )
        self._address = address
        self._capabilities = capabilities
        self._intent_nl = intent_nl

        self._fabric = fabric

    # FameService plumbing
    # --------------------
    @property
    def name(self) -> str: ...

    @property
    def spec(self) -> dict[str, Any]:
        return {"address": str(self._address)}

    @property
    def address(self) -> Optional[FameAddress]:  # type: ignore[override]
        return self._address

    # Metadata helpers (proxy side only)
    # ----------------------------------
    async def get_agent_card(self) -> AgentCard:  # pragma: no cover
        """Fetch the remote agent's metadata card.

        Raises:
            NotImplementedError: Not yet implemented.
        """
        raise NotImplementedError("Fetching remote AgentCard not yet implemented.")

    def authenticate(self, credentials: AuthenticationInfo) -> bool:  # pragma: no cover
        """Authenticate with the remote agent.

        Args:
            credentials: Authentication credentials.

        Raises:
            NotImplementedError: Proxy authentication is not supported.
        """
        raise NotImplementedError("Proxy authentication not supported.")

    async def run_task(
        self,
        payload: dict[str, Any] | str | None = None,
        id: str | None = None,
    ) -> Any:
        """Execute a task on the remote agent and wait for completion.

        Starts a task, subscribes to updates, and returns the final result.
        For long-running tasks, consider using :meth:`start_task` and
        :meth:`subscribe_to_task_updates` separately.

        Args:
            payload: Input data as a dict or string.
            id: Optional task id (auto-generated if omitted).

        Returns:
            The task result extracted from the completion message.

        Raises:
            ValueError: If the task fails or returns an unrecognized part type.
        """
        task_id = id or generate_id()
        task_params = make_task_params(id=task_id, payload=payload)
        result = await self.start_task(task_params)

        status: TaskStatus = result.status
        if result.status.state not in TERMINAL_TASK_STATES:
            update_events = await self.subscribe_to_task_updates(
                make_task_params(id=task_id)
            )
            try:
                async for update_event in update_events:
                    if isinstance(update_event, TaskStatusUpdateEvent):
                        if update_event.status.state in TERMINAL_TASK_STATES:
                            status = update_event.status

                            break  # TODO?
            finally:
                # even if we raise, make sure the generator’s finally runs
                if update_events is not None:
                    await cast(AsyncGenerator, update_events).aclose()

        if status.state == TaskState.FAILED:
            message = status.message if status.message else None
            error = first_text_part(message) or "Unknown error"
            raise ValueError(error)

        if not status.message:
            return None

        parts = status.message.parts

        if not parts:
            return None

        first = parts[0]
        if isinstance(first, TextPart):
            payload = first.text
        elif isinstance(first, DataPart):
            payload = first.data
        else:
            raise ValueError(f"Don't know how to extract payload from part: {first}")

        return payload

    @overload
    async def start_task(self, params: TaskSendParams) -> Task: ...

    @overload
    async def start_task(
        self,
        *,
        id: str,
        role: Literal["user", "agent"] = "agent",
        payload: dict[str, Any] | str,
        session_id: Optional[str] = None,
        accepted_output_modes: Optional[List[str]] = None,
        push_notification: Optional[PushNotificationConfig] = None,
        history_length: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Task: ...

    async def start_task(self, *args: Any, **kwargs: Any) -> Task:  # type: ignore[override]
        # Classic signature
        if args and isinstance(args[0], TaskSendParams):
            if len(args) > 1 or kwargs:
                raise TypeError(
                    "When passing TaskSendParams positionally, do not add extras."
                )
            params: TaskSendParams = args[0]  # type: ignore
        else:
            # Convenience signature
            if args:
                raise TypeError(
                    f"Keyword-only overload: unexpected positional arguments {args!r}"
                )
            task_params = kwargs.pop("params", None)
            if isinstance(task_params, TaskSendParams):
                if kwargs:
                    raise TypeError(
                        "Keyword-only overload: unexpected keywords arguments "
                        f"{kwargs!r}"
                    )
                params = task_params
            else:
                params = make_task_params(**kwargs)  # type: ignore[arg-type]

        result = await self._invoke_target(
            "tasks/send", params.model_dump(by_alias=True)
        )
        return Task.model_validate(result)

    # -- Remaining lifecycle helpers -------------------------------------- #
    async def get_task_status(self, params: TaskQueryParams) -> Task:
        """Query the status of a task on the remote agent.

        Args:
            params: Query parameters with the task id.

        Returns:
            Task object with current status.
        """
        result = await self._invoke_target(
            "tasks/get", params.model_dump(by_alias=True)
        )
        return Task.model_validate(result)

    async def cancel_task(self, params: TaskIdParams) -> Task:
        """Cancel a task on the remote agent.

        Args:
            params: Parameters with the task id.

        Returns:
            Task object with CANCELED status.
        """
        result = await self._invoke_target(
            "tasks/cancel", params.model_dump(by_alias=True)
        )
        return Task.model_validate(result)

    async def _stream_rpc(
        self,
        method: str,
        params: Dict[str, Any],
        *,
        parse_frame: Callable[[Dict[str, Any]], R],
        unsubscribe_method: str,
        unsubscribe_params: Dict[str, Any],
        timeout_ms: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncIterator[R]:
        rpc_iter = await self._invoke_target(method, params, streaming=True)
        rpc_aiter = rpc_iter.__aiter__()
        count = 0

        try:
            while True:
                try:
                    # apply timeout if requested
                    if timeout_ms is not None:
                        raw = await asyncio.wait_for(
                            rpc_aiter.__anext__(),
                            timeout_ms / 1000.0,
                        )
                    else:
                        raw = await rpc_aiter.__anext__()
                except asyncio.TimeoutError:
                    # no new frame within timeout → end stream
                    break
                except StopAsyncIteration:
                    break

                # # error sentinel
                # if raw.error:
                #     raise AgentException(raw.error)
                # end-of-stream sentinel
                if raw is None:
                    break

                if max_items is not None and count >= max_items:
                    break

                yield parse_frame(raw)
                count += 1

        finally:
            await self._invoke_target(
                unsubscribe_method,
                unsubscribe_params,
            )

    async def subscribe_to_task_updates(
        self,
        params: TaskSendParams,
        *,
        timeout_ms: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> AsyncIterator[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]:
        """Subscribe to live task updates from the remote agent.

        Streams status and artifact events until the task completes or
        the timeout/max_items limit is reached.

        Args:
            params: Parameters with the task id.
            timeout_ms: Optional timeout in milliseconds between events.
            max_items: Optional maximum number of events to receive.

        Yields:
            TaskStatusUpdateEvent or TaskArtifactUpdateEvent objects.
        """
        return self._stream_rpc(
            "tasks/sendSubscribe",
            params.model_dump(by_alias=True),
            parse_frame=lambda p: (
                TaskArtifactUpdateEvent.model_validate(p)
                if "artifact" in p
                else TaskStatusUpdateEvent.model_validate(p)
            ),
            unsubscribe_method="tasks/sendUnsubscribe",
            unsubscribe_params=TaskIdParams(id=params.id).model_dump(by_alias=True),
            timeout_ms=timeout_ms,
            max_items=max_items,
        )

    async def unsubscribe_task(self, params: TaskIdParams) -> Any:
        """Stop receiving updates for a task.

        Args:
            params: Parameters with the task id.

        Returns:
            Server acknowledgment.
        """
        result = await self._invoke_target(
            "tasks/sendUnsubscribe",
            params.model_dump(by_alias=True),
        )
        return result

    async def register_push_endpoint(
        self, config: TaskPushNotificationConfig
    ) -> TaskPushNotificationConfig:
        """Register a push notification endpoint for task updates.

        Args:
            config: Push notification configuration with endpoint URL.

        Returns:
            Confirmed push notification configuration.
        """
        result = await self._invoke_target(
            "tasks/pushNotification/set",
            config.model_dump(by_alias=True),
        )
        return TaskPushNotificationConfig.model_validate(result)

    async def get_push_notification_config(
        self, params: TaskIdParams
    ) -> TaskPushNotificationConfig:
        """Get the push notification configuration for a task.

        Args:
            params: Parameters with the task id.

        Returns:
            Current push notification configuration.
        """
        result = await self._invoke_target(
            "tasks/pushNotification/get",
            params.model_dump(by_alias=True),
        )
        return TaskPushNotificationConfig.model_validate(result)

    # ------------------------------------------------------------------ #
    async def _invoke_target(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        streaming: bool = False,
    ):
        """Internal: Route RPC calls to the appropriate fabric method.

        Selects the correct invocation path based on how this proxy was
        constructed (address vs capabilities vs intent).

        Args:
            method: RPC method name (e.g., 'tasks/send').
            params: Method parameters.
            streaming: Whether to return a streaming iterator.

        Returns:
            RPC result or async iterator for streaming calls.

        Raises:
            RuntimeError: If no routing target is configured.
        """
        if self._address:
            if streaming:
                return await self._fabric.invoke_stream(
                    self._address, method, params or {}
                )
            return await self._fabric.invoke(self._address, method, params or {})

        if self._capabilities:
            if streaming:
                return await self._fabric.invoke_by_capability_stream(
                    self._capabilities, method, params or {}
                )
            return await self._fabric.invoke_by_capability(
                self._capabilities, method, params or {}
            )

        # # future: intent-based routing
        # if self._intent_nl:
        #     if streaming:
        #         return await self._fabric.invoke_by_intent_stream(
        #             self._intent_nl, method, params or {}
        #         )
        #     return await self._fabric.invoke_by_intent(
        #         self._intent_nl, method, params or {}
        #     )

        # should never happen because of constructor guard
        raise RuntimeError("Proxy has no routing target")
