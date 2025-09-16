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


Payload = dict[str, Any] | str | None
Targets = Iterable[tuple[FameAddress | str, Payload]]


class Agent(RpcMixin, FameService, ABC):
    """Base interface every on-fabric agent must fulfil."""

    # -- Metadata --------------------------------------------------------- #
    @property
    @abstractmethod
    def name(self) -> Optional[str]: ...

    @property
    @abstractmethod
    def spec(self) -> dict[str, Any]: ...

    # -- Identity / auth -------------------------------------------------- #
    @abstractmethod
    async def get_agent_card(self) -> AgentCard: ...

    @abstractmethod
    def authenticate(self, credentials: AuthenticationInfo) -> bool: ...

    # -- Task lifecycle --------------------------------------------------- #
    @abstractmethod
    async def start_task(self, params: TaskSendParams) -> Task: ...

    @abstractmethod
    async def run_task(
        self,
        payload: dict[str, Any] | str | None,
        id: str | None,
    ) -> Any: ...

    @abstractmethod
    async def get_task_status(self, params: TaskQueryParams) -> Task: ...

    @abstractmethod
    async def cancel_task(self, params: TaskIdParams) -> Task: ...

    @abstractmethod
    async def subscribe_to_task_updates(
        self, params: TaskSendParams
    ) -> AsyncIterator[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]: ...

    @abstractmethod
    async def unsubscribe_task(self, params: TaskIdParams) -> Any: ...

    # -- Push notifications ---------------------------------------------- #
    @abstractmethod
    async def register_push_endpoint(
        self, config: TaskPushNotificationConfig
    ) -> TaskPushNotificationConfig: ...

    @abstractmethod
    async def get_push_notification_config(
        self, params: TaskIdParams
    ) -> TaskPushNotificationConfig: ...

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
        """
        Return a typed proxy to a remote agent.
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
        """
        Return a typed proxy to a remote agent.
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
        """
        Return a typed proxy to a remote agent.
        """
        from naylence.agent.agent_proxy import AgentProxy

        return AgentProxy[TAgent](
            capabilities=capabilities, fabric=fabric or FameFabric.current()
        )

    @staticmethod
    def from_handler(
        handler: Callable[[dict[str, Any] | str | None, str | None], Awaitable[Any]],
    ) -> "Agent":
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
        return await cls.run_many([(a, payload) for a in addresses], **kw)

    @classmethod
    async def run_many(
        cls: Type[TAgent],
        targets: Targets,
        *,
        fabric: FameFabric | None = None,
        gather_exceptions: bool = True,
    ) -> list[tuple[str, Any | Exception]]:
        """
        Scatter-gather helper: run_task() once per (address, payload) pair.

        Returns a list ordered like *targets*, containing
            (str(address), result | Exception)
        so the caller can decide how to post-process.
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
        """
        Synchronous entry-point:
        - if there's already an event loop running, schedule our coroutine on it and return the Task;
        - otherwise, block in `asyncio.run()` until it finishes.
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
