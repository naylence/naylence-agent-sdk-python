import asyncio
from typing import Any, AsyncIterator, Dict, Optional

from naylence.fame.core import (
    AGENT_CAPABILITY,
    DataFrame,
    DeliveryAckFrame,
    FameAddress,
    FameDeliveryContext,
    FameEnvelope,
    FameFabric,
    FameMessageResponse,
    create_fame_envelope,
    generate_id,
)
from naylence.fame.util import logging

from naylence.agent.a2a_types import (
    AgentCard,
    AuthenticationInfo,
    DataPart,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskSendParams,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)
from naylence.agent.agent import Agent
from naylence.agent.errors import (
    PushNotificationNotSupportedException,
    TaskNotCancelableException,
    UnsupportedOperationException,
)
from naylence.agent.rpc_adapter import handle_agent_rpc_request
from naylence.agent.util import decode_fame_data_payload, make_task
from naylence.fame.storage.storage_provider import (
    StorageProvider,
)

logger = logging.getLogger(__name__)


TERMINAL_TASK_STATES = {
    TaskState.COMPLETED,
    TaskState.CANCELED,
    TaskState.FAILED,
}


class BaseAgent(Agent):
    def __init__(self, name: str | None = None):
        self._name = name or generate_id()
        self._address = None
        self._capabilities = [AGENT_CAPABILITY]
        self._subscriptions: dict[str, asyncio.Task] = {}  # id → Task
        self._storage_provider: Optional[StorageProvider] = None

    @property
    def capabilities(self):
        return self._capabilities

    @property
    def name(self) -> str:
        return self._name

    @property
    def spec(self) -> Dict:
        return {"address": self._address}

    @property
    def address(self) -> Optional[FameAddress]:
        return self._address

    @address.setter
    def address(self, address: FameAddress):
        self._address = address

    @property
    def storage_provider(self) -> Optional[StorageProvider]:
        if not self._storage_provider:
            from naylence.fame.node.node import get_node

            node = get_node()
            self._storage_provider = node.storage_provider

        return self._storage_provider

    @staticmethod
    def _is_rpc_request(raw_message: Any):
        return (
            isinstance(raw_message, dict)
            and "jsonrpc" in raw_message
            and "method" in raw_message
            and "params" in raw_message
        )

    async def __call__(self, *args: Any, **kwds: Any) -> Any:
        raise UnsupportedOperationException(
            f"Agent {self} does not support operation '__call__'"
        )

    async def handle_message(
        self, envelope: FameEnvelope, context: Optional[FameDeliveryContext] = None
    ) -> Optional[FameMessageResponse | AsyncIterator[FameMessageResponse]]:
        if isinstance(envelope.frame, DeliveryAckFrame):
            logger.debug("received_delivery_ack", delivery_ack_frame=envelope.frame)
            if envelope.frame.ok:
                logger.trace(
                    "positive_delivery_ack",
                    corr_id=envelope.corr_id,
                )
                return None
            task_id = envelope.corr_id
            if task_id:
                task = self._subscriptions.get(task_id)
                if task and not task.done():
                    logger.info("cancelling_stream_on_nack", task_id=task_id)
                    task.cancel()
            return None
        if not isinstance(envelope.frame, DataFrame):
            raise RuntimeError(
                f"Invalid envelope frame. Expected {DataFrame}, actual: {type(envelope.frame)}"
            )
        decoded_payload = decode_fame_data_payload(envelope.frame)
        if BaseAgent._is_rpc_request(decoded_payload):
            return await self._handle_rpc_message(
                decoded_payload, envelope.reply_to, envelope.trace_id
            )

        return await self.on_message(decoded_payload)

    async def on_message(self, message: Any) -> Optional[FameMessageResponse]:
        """Override to process any *non-RPC* inbound message delivered by the Fabric.

        Examples include push notifications, alerts, or custom application signals. The
        default implementation just logs the payload.
        """
        logger.info("Unhandled inbound message: %s", message)
        return None  # No response by default

    async def _handle_rpc_message(
        self,
        rpc_request: dict,
        reply_to: Optional[FameAddress] = None,
        trace_id: Optional[str] = None,
    ) -> Optional[FameMessageResponse | AsyncIterator[FameMessageResponse]]:
        # ⏩ For a long‐lived subscribe, stream in the background so we don't block the recv loop
        if rpc_request.get("method") == "tasks/sendSubscribe":
            # spawn the generator+send in its own task and return immediately
            task = asyncio.create_task(
                self._stream_send_subscribe(rpc_request, reply_to)
            )
            id = rpc_request.get("id")
            if id:
                self._subscriptions[id] = task
            return

        # For all other RPCs, return an async generator that wraps each response in FameMessageResponse
        async def _rpc_response_generator():
            response_iter = handle_agent_rpc_request(self, rpc_request)
            async for rpc_response in response_iter:
                reply_to_addr = reply_to or rpc_request["params"].get("reply_to")
                if not reply_to_addr:
                    logger.warning("Missing reply_to in request")
                    break

                frame = DataFrame(payload=rpc_response)
                envelope = create_fame_envelope(
                    frame=frame,
                    to=reply_to_addr,
                    trace_id=trace_id,
                    corr_id=rpc_request.get("id"),
                    # response_type=FameResponseType.ACK # not yet
                )
                yield FameMessageResponse(envelope=envelope)

        return _rpc_response_generator()

    async def _stream_send_subscribe(self, rpc_request, reply_to):
        """
        Drain the subscribe generator without holding up the main recv loop.
        """
        try:
            async for rpc_response in handle_agent_rpc_request(self, rpc_request):
                target = reply_to or rpc_request["params"].get("reply_to")
                if not target:
                    logger.warning("Missing reply_to in sendSubscribe stream")
                    return

                frame = DataFrame(payload=rpc_response)
                env = create_fame_envelope(
                    frame=frame, to=target, corr_id=rpc_request.get("id")
                )
                await FameFabric.current().send(env)
        except asyncio.CancelledError:
            logger.debug("send_subscribed_cancelled", rpc_request["id"])
            raise
        finally:
            self._subscriptions.pop(rpc_request["id"], None)  # drop registry entry

    def authenticate(self, credentials: AuthenticationInfo) -> bool:
        return True  # No auth by default

    async def register_push_endpoint(
        self, config: TaskPushNotificationConfig
    ) -> TaskPushNotificationConfig:
        raise PushNotificationNotSupportedException()

    async def get_push_notification_config(
        self, params: TaskIdParams
    ) -> TaskPushNotificationConfig:
        raise PushNotificationNotSupportedException()

    async def subscribe_to_task_updates(
        self, params: TaskSendParams
    ) -> AsyncIterator[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]:
        """
        Default fallback: poll get_task_status every 500 ms until terminal.
        """

        # inner async-generator does the actual yielding
        async def _stream() -> AsyncIterator[
            TaskStatusUpdateEvent | TaskArtifactUpdateEvent
        ]:
            last_state = None
            while True:
                task = await self.get_task_status(TaskQueryParams(id=params.id))
                # only yield on state-change
                if task.status.state != last_state:
                    yield TaskStatusUpdateEvent(**task.model_dump())
                    last_state = task.status.state

                if task.status.state in TERMINAL_TASK_STATES:
                    break

                await asyncio.sleep(0.5)

        return _stream()

    async def unsubscribe_task(self, params: TaskIdParams) -> Any:
        raise UnsupportedOperationException(
            f"Agent {self} does not support operation 'unsubscribe_task'"
        )

    async def cancel_task(self, params: TaskIdParams) -> Task:
        raise TaskNotCancelableException()

    async def get_agent_card(self) -> AgentCard:
        raise UnsupportedOperationException(
            f"Agent {self} does not support operation 'get_agent_card'"
        )

    async def get_task_status(self, params: TaskQueryParams) -> Task:
        raise UnsupportedOperationException(
            f"Agent {self} does not support operation 'get_task_status'"
        )

    async def run_task(
        self,
        payload: dict[str, Any] | str | None,
        id: str | None,
    ) -> Any:
        raise UnsupportedOperationException(
            f"Agent {self} does not support operation 'run_task'"
        )

    # ------------------------------------------------------------------ #
    #  (3)  Canonical signature required by Agent
    # ------------------------------------------------------------------ #
    async def start_task(self, params: TaskSendParams) -> Task:  # type: ignore[override]
        cls = self.__class__

        # --- Path A: subclass provided its own start_task ----------------
        if BaseAgent.start_task is not cls.start_task:
            return await cls.start_task(self, params)  # type: ignore[misc]

        # --- Path C: fallback to run_task -----------------------------
        if BaseAgent.run_task is not cls.run_task:
            parts = params.message.parts
            payload = None
            if parts:
                first = parts[0]
                if isinstance(first, TextPart):
                    payload = first.text
                elif isinstance(first, DataPart):
                    payload = first.data

            response_payload = await self.run_task(
                payload=payload,
                id=params.id,
            )

            return make_task(
                id=params.id,
                state=TaskState.COMPLETED,
                payload=response_payload,
            )

        # --- None of the above implemented ------------------------------
        raise NotImplementedError(
            f"{cls.__name__} must implement at least one of: "
            "`start_task()`, `start_task_simple()`, or `run_task()`."
        )
