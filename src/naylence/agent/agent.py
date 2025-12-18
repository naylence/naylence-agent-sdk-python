"""Agent module providing the abstract Agent class.

An Agent is a self-contained unit of work that can receive tasks, process them,
and return results. Agents communicate over the Fame fabric using a standard
task-based protocol.

For concrete implementations:
    - Use :class:`BaseAgent` when you need full control over task handling and state.
    - Use :class:`BackgroundTaskAgent` for long-running or async background work.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Optional,
    Type,
    TypeVar,
)

from naylence.fame.core import FameAddress, FameFabric, FameService, generate_id
from naylence.fame.service import RpcMixin

from naylence.agent.a2a_types import (
    AgentCard,
    AuthenticationInfo,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskSendParams,
    TaskStatusUpdateEvent,
)

if TYPE_CHECKING:
    # only for the type‐checker, never at runtime
    from naylence.agent.agent_proxy import AgentProxy

from naylence.fame.util import logging

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Typing helpers
# --------------------------------------------------------------------------- #

TAgent = TypeVar("TAgent", bound="Agent")

# --------------------------------------------------------------------------- #
#  Abstract Agent
# --------------------------------------------------------------------------- #

#: Payload type for agent task messages. Can be a dict, string, or None.
Payload = dict[str, Any] | str | None

#: Collection of address-payload pairs for broadcasting tasks to multiple agents.
Targets = Iterable[tuple[FameAddress | str, Payload]]


class Agent(RpcMixin, FameService, ABC):
    """Abstract base class for all agents.

    Agents are addressable services that handle tasks over the Fame fabric.
    This class defines the core protocol methods every agent must implement.

    Do not extend Agent directly. Instead:
        - Extend :class:`BaseAgent` for standard request-response agents.
        - Extend :class:`BackgroundTaskAgent` for long-running background work.

    Use :meth:`Agent.remote` or :meth:`Agent.remote_by_address` to create proxies
    for communicating with remote agents.

    Example:
        >>> from naylence.agent import BaseAgent, Payload
        >>>
        >>> class EchoAgent(BaseAgent):
        ...     async def run_task(self, payload: Payload, id: str | None) -> Payload:
        ...         return payload
        >>>
        >>> agent = EchoAgent("echo")
        >>> await agent.aserve("fame://echo")
    """

    # -- Metadata --------------------------------------------------------- #
    @property
    @abstractmethod
    def name(self) -> Optional[str]:
        """The agent's name, used for logging and identification."""

    @property
    @abstractmethod
    def spec(self) -> dict[str, Any]:
        """Returns metadata about this agent (address, capabilities, etc.)."""

    # -- Identity / auth -------------------------------------------------- #
    @abstractmethod
    async def get_agent_card(self) -> AgentCard:
        """Returns the agent's card describing its capabilities and metadata."""

    @abstractmethod
    def authenticate(self, credentials: AuthenticationInfo) -> bool:
        """Validates authentication credentials.

        Args:
            credentials: The credentials to validate.

        Returns:
            True if authentication succeeds.
        """

    # -- Task lifecycle --------------------------------------------------- #
    @abstractmethod
    async def start_task(self, params: TaskSendParams) -> Task:
        """Initiates a new task.

        Args:
            params: Task parameters including message and optional metadata.

        Returns:
            The created task with its initial status.
        """

    @abstractmethod
    async def run_task(
        self,
        payload: dict[str, Any] | str | None,
        id: str | None,
    ) -> Any:
        """Execute a task synchronously and return the result.

        Args:
            payload: Input data from the task request.
            id: Task identifier.

        Returns:
            Result to include in the task completion message.
        """
        ...

    @abstractmethod
    async def get_task_status(self, params: TaskQueryParams) -> Task:
        """Get the current status of a task.

        Args:
            params: Query parameters with the task id.

        Returns:
            Task object with current status.
        """
        ...

    @abstractmethod
    async def cancel_task(self, params: TaskIdParams) -> Task:
        """Cancel a running task.

        Args:
            params: Parameters with the task id.

        Returns:
            Task object with CANCELED status.
        """
        ...

    @abstractmethod
    async def subscribe_to_task_updates(
        self, params: TaskSendParams
    ) -> AsyncIterator[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]:
        """Subscribe to live task status and artifact updates.

        Args:
            params: Parameters with the task id.

        Yields:
            TaskStatusUpdateEvent or TaskArtifactUpdateEvent objects.
        """
        ...

    @abstractmethod
    async def unsubscribe_task(self, params: TaskIdParams) -> Any:
        """Stop receiving updates for a task.

        Args:
            params: Parameters with the task id.

        Returns:
            Server acknowledgment.
        """
        ...

    # -- Push notifications ---------------------------------------------- #
    @abstractmethod
    async def register_push_endpoint(
        self, config: TaskPushNotificationConfig
    ) -> TaskPushNotificationConfig:
        """Registers a push notification endpoint for task updates.

        Args:
            config: Push notification configuration.

        Returns:
            The registered configuration.
        """

    @abstractmethod
    async def get_push_notification_config(
        self, params: TaskIdParams
    ) -> TaskPushNotificationConfig:
        """Retrieves the push notification config for a task.

        Args:
            params: Parameters including the task ID.

        Returns:
            The push notification configuration.
        """

    # --------------------------------------------------------------------- #
    #  Remote proxy constructor
    # --------------------------------------------------------------------- #
    @classmethod
    def remote(
        cls: Type[TAgent],
        *,
        address: Optional[FameAddress | str] = None,
        capabilities: Optional[list[str]] = None,
        fabric: Optional[FameFabric] = None,
        **kwargs,
    ) -> "AgentProxy[TAgent]":
        """Creates a proxy for communicating with a remote agent.

        Provide exactly one of ``address`` or ``capabilities``.

        Args:
            address: Direct address of the target agent.
            capabilities: Required capabilities for discovery.
            fabric: Fabric instance to use. Defaults to the current fabric.

        Returns:
            A proxy for the remote agent.

        Raises:
            ValueError: If both or neither of address/capabilities are provided.

        Example:
            >>> proxy = Agent.remote(address="fame://echo")
            >>> result = await proxy.run_task("hello")
        """
        chosen = sum(x is not None for x in (address, capabilities))
        if chosen != 1:
            raise ValueError("Provide exactly one of address | capabilities")

        if address is not None:
            address = (
                address if isinstance(address, FameAddress) else FameAddress(address)
            )
        from naylence.agent.agent_proxy import AgentProxy

        return AgentProxy[TAgent](
            address=address,
            capabilities=capabilities,
            fabric=fabric or FameFabric.current(),
        )

    @classmethod
    def remote_by_address(
        cls: Type[TAgent],
        address: FameAddress | str,
        *,
        fabric: Optional[FameFabric] = None,
        **kwargs,
    ) -> "AgentProxy[TAgent]":
        """Creates a proxy for a remote agent by its address.

        Args:
            address: The target agent's address.
            fabric: Optional fabric configuration.

        Returns:
            A proxy for the remote agent.
        """
        address = address if isinstance(address, FameAddress) else FameAddress(address)
        from naylence.agent.agent_proxy import AgentProxy

        return AgentProxy[TAgent](
            address=address, fabric=fabric or FameFabric.current()
        )

    @classmethod
    def remote_by_capabilities(
        cls: Type[TAgent],
        capabilities: list[str],
        *,
        fabric: Optional[FameFabric] = None,
        **kwargs,
    ) -> "AgentProxy[TAgent]":
        """Creates a proxy for a remote agent by required capabilities.

        Args:
            capabilities: Required capabilities for discovery.
            fabric: Optional fabric configuration.

        Returns:
            A proxy for a matching remote agent.
        """
        from naylence.agent.agent_proxy import AgentProxy

        return AgentProxy[TAgent](
            capabilities=capabilities, fabric=fabric or FameFabric.current()
        )

    @staticmethod
    def from_handler(
        handler: Callable[[dict[str, Any] | str | None, str | None], Awaitable[Any]],
    ) -> "Agent":
        """Creates an agent from a simple handler function.

        Useful for quick prototyping without defining a full agent class.

        Args:
            handler: Async function that processes task payloads.

        Returns:
            A new agent instance wrapping the handler.
        """
        from .base_agent import BaseAgent

        class AgentImpl(BaseAgent):
            def __init__(self):
                super().__init__(name=generate_id())

            async def run_task(
                self, payload: dict[str, Any] | str | None, id: str | None
            ) -> Any:
                return await handler(payload, id)

        return AgentImpl()

    @classmethod
    async def broadcast(
        cls, addresses: list[FameAddress | str], payload: Payload = None, **kw
    ) -> list[tuple[str, Any | Exception]]:
        """Sends the same payload to multiple agents.

        Args:
            addresses: List of agent addresses.
            payload: Payload to send to all agents.
            **kw: Additional options passed to :meth:`run_many`.

        Returns:
            List of (address, result_or_error) tuples.
        """
        return await cls.run_many([(a, payload) for a in addresses], **kw)

    @classmethod
    async def run_many(
        cls: Type[TAgent],
        targets: Targets,
        *,
        fabric: FameFabric | None = None,
        gather_exceptions: bool = True,
    ) -> list[tuple[str, Any | Exception]]:
        """Runs tasks on multiple agents with individual payloads.

        Args:
            targets: Iterable of (address, payload) pairs.
            fabric: Fabric instance to use. Defaults to the current fabric.
            gather_exceptions: If True (default), errors are collected alongside
                results. If False, the first error raises immediately.

        Returns:
            List of (address, result_or_error) tuples, ordered like targets.
        """
        proxies: dict[str, AgentProxy[TAgent]] = {}
        coros: list[Awaitable[Any]] = []
        addr_list: list[str] = []

        for address, payload in targets:
            addr_str = str(address)
            if addr_str not in proxies:
                proxies[addr_str] = cls.remote_by_address(address, fabric=fabric)
            coros.append(proxies[addr_str].run_task(payload, generate_id()))
            addr_list.append(addr_str)

        results = await asyncio.gather(*coros, return_exceptions=gather_exceptions)
        return list(zip(addr_list, results))

    async def aserve(
        self,
        address: FameAddress | str,
        *,
        log_level: str | int | None = None,
        **kwargs,
    ):
        """Starts serving this agent at the given address (async version).

        Listens for SIGINT/SIGTERM to shut down gracefully.
        The method returns when the agent stops serving.

        Args:
            address: The address to serve at (e.g., 'fame://my-agent').
            log_level: Optional log level for the agent.
            **kwargs: Additional options passed to FameFabric.get_or_create().
        """
        stop_evt = asyncio.Event()
        loop = asyncio.get_running_loop()

        if log_level:
            logging.enable_logging(log_level)

        import signal

        loop.add_signal_handler(signal.SIGINT, stop_evt.set)
        loop.add_signal_handler(signal.SIGTERM, stop_evt.set)

        async with FameFabric.get_or_create(**kwargs) as fabric:
            await fabric.serve(self, address)
            logger.info(f"{self.__class__.__name__} is live!  Press Ctrl+C to stop.")
            await stop_evt.wait()
            logger.info("⏳ Shutting down…")

    def serve(
        self,
        address: FameAddress | str,
        **kwargs: Any,
    ):
        """Starts serving this agent at the given address (sync entry point).

        If there is already an event loop running, schedules the coroutine on it
        and returns a Task. Otherwise, blocks in asyncio.run() until finished.

        Args:
            address: The address to serve at.
            **kwargs: Options passed to :meth:`aserve`.

        Returns:
            An asyncio.Task if a loop is running, otherwise None.
        """
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop:
            return loop.create_task(self.aserve(address, **kwargs))
        else:
            return asyncio.run(self.aserve(address, **kwargs))
