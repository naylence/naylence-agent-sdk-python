import logging
from typing import AsyncIterator, Dict

from naylence.agent.a2a_types import (
    A2ARequest,
    InternalError,
    InvalidParamsError,
    InvalidRequestError,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MethodNotFoundError,
    PushNotificationNotSupportedError,
    TaskNotCancelableError,
    UnsupportedOperationError,
)
from naylence.agent.agent import Agent
from naylence.agent.errors import (
    AgentException,
    AuthorizationException,
    ConflictException,
    DuplicateTaskException,
    InvalidDataException,
    InvalidTaskException,
    NoDataFoundException,
    PushNotificationNotSupportedException,
    RateLimitExceededException,
    TaskNotCancelableException,
    UnsupportedOperationException,
)
from naylence.agent.util import extract_id

logger = logging.getLogger(__name__)

A2A_METHODS = [
    "tasks/send",
    "tasks/sendSubscribe",
    "tasks/sendUnsubscribe",
    "tasks/get",
    "tasks/cancel",
    "tasks/pushNotification/set",
    "tasks/pushNotification/get",
    "tasks/resubscribe",
]


async def handle_agent_rpc_request(
    agent: Agent, raw_rpc_request: Dict
) -> AsyncIterator[JSONRPCResponse]:
    # ---- 1 · generic JSON-RPC validation ----------------------------------
    try:
        generic_req: JSONRPCRequest = JSONRPCRequest.model_validate(raw_rpc_request)
    except Exception as e:
        yield JSONRPCResponse(
            id=raw_rpc_request.get("id"), error=InvalidRequestError(data=str(e))
        )
        return

    # ---- 2 · built-in A2A operations --------------------------------------
    if generic_req.method in A2A_METHODS:
        async for res in handle_a2a_rpc_request(agent, raw_rpc_request):
            yield res
        return

    # ---- 3 · custom @rpc operations --------------------------------------
    async for res in handle_custom_rpc_request(agent, generic_req):
        yield res
    return


async def handle_a2a_rpc_request(
    agent: Agent, raw_rpc_request: Dict
) -> AsyncIterator[JSONRPCResponse]:
    try:
        a2a_req: JSONRPCRequest = A2ARequest.validate_python(raw_rpc_request)
    except Exception as e:
        yield JSONRPCResponse(
            id=extract_id(raw_rpc_request), error=InvalidRequestError(data=str(e))
        )
        return

    params = a2a_req.params

    try:
        match a2a_req.method:
            case "tasks/send":
                result = await agent.start_task(params)
                yield JSONRPCResponse(
                    id=a2a_req.id, result=result.model_dump(by_alias=True)
                )
            case "tasks/get":
                result = await agent.get_task_status(params)
                yield JSONRPCResponse(
                    id=a2a_req.id, result=result.model_dump(by_alias=True)
                )
            case "tasks/cancel":
                result = await agent.cancel_task(params)
                yield JSONRPCResponse(
                    id=a2a_req.id, result=result.model_dump(by_alias=True)
                )
            case "tasks/pushNotification/set":
                result = await agent.register_push_endpoint(params)
                yield JSONRPCResponse(
                    id=a2a_req.id, result=result.model_dump(by_alias=True)
                )
            case "tasks/pushNotification/get":
                result = await agent.get_push_notification_config(params)
                yield JSONRPCResponse(
                    id=a2a_req.id, result=result.model_dump(by_alias=True)
                )
            case "agent.get_card":
                result = await agent.get_agent_card()
                yield JSONRPCResponse(
                    id=a2a_req.id, result=result.model_dump(by_alias=True)
                )
            case "tasks/sendSubscribe":
                # call into your agent logic
                async for evt in await agent.subscribe_to_task_updates(params):
                    # model_dump() will include by_alias mapping for status|artifact fields
                    yield JSONRPCResponse(
                        id=a2a_req.id,
                        result=evt.model_dump(by_alias=True),
                    )
                # end-of-stream sentinel:
                yield JSONRPCResponse(
                    id=a2a_req.id,
                    result=None,  # <— this tells invoke_stream “no more frames”
                )
            case "tasks/sendUnsubscribe":
                # immediate cleanup of the queue on the agent side
                await agent.unsubscribe_task(params)
                yield JSONRPCResponse(id=a2a_req.id, result=None)

            case _:
                yield JSONRPCResponse(id=a2a_req.id, error=MethodNotFoundError())

    except InvalidTaskException as e:
        yield JSONRPCResponse(id=a2a_req.id, error=InvalidParamsError(data=str(e)))
    except (DuplicateTaskException, ConflictException) as e:
        # “409 conflict” style
        yield JSONRPCResponse(id=a2a_req.id, error=InvalidParamsError(data=str(e)))
    except NoDataFoundException as e:
        yield JSONRPCResponse(id=a2a_req.id, error=InvalidParamsError(data=str(e)))
    except InvalidDataException as e:
        yield JSONRPCResponse(id=a2a_req.id, error=InvalidParamsError(data=str(e)))
    except TaskNotCancelableException:
        yield JSONRPCResponse(id=a2a_req.id, error=TaskNotCancelableError())
    except PushNotificationNotSupportedException:
        yield JSONRPCResponse(id=a2a_req.id, error=PushNotificationNotSupportedError())
    except UnsupportedOperationException as e:
        yield JSONRPCResponse(
            id=a2a_req.id, error=UnsupportedOperationError(message=str(e))
        )
    except AuthorizationException as e:
        # use JSONRPC “-32600” or whichever fits
        yield JSONRPCResponse(
            id=a2a_req.id,
            error=JSONRPCError(code=-32600, message="Unauthorized", data=str(e)),
        )
    except RateLimitExceededException as e:
        yield JSONRPCResponse(
            id=a2a_req.id,
            error=JSONRPCError(code=-32029, message="Rate limit exceeded", data=str(e)),
        )
    except AgentException as e:
        # default handler for any other AgentError
        yield JSONRPCResponse(id=a2a_req.id, error=InternalError(data=str(e)))
    except Exception as e:
        # catch *everything* else
        logger.error(f"Internal error: {e}", exc_info=True)
        yield JSONRPCResponse(id=a2a_req.id, error=InternalError(data=str(e)))

    return


def _normalize(p):
    """
    FameServiceProxy sends:
        { "args": (<positional args>, …), "kwargs": {…} }
    For backward compatibility, collapse that into (*args, **kwargs).
    """
    if isinstance(p, dict) and ("args" in p or "kwargs" in p):
        args = p.get("args", [])
        kwargs = p.get("kwargs", {})
        if not isinstance(args, (list, tuple)):
            args = [args]
        return args, kwargs
    return [], p  # plain-kwargs case


async def handle_custom_rpc_request(
    agent: Agent, custom_req: JSONRPCRequest
) -> AsyncIterator[JSONRPCResponse]:
    registry = agent.__class__._rpc_registry
    if custom_req.method not in registry:
        yield JSONRPCResponse(id=custom_req.id, error=MethodNotFoundError())
        return

    attr, streaming = registry[custom_req.method]

    args, kwargs = _normalize(custom_req.params or {})
    handler = getattr(agent, attr)

    try:
        if streaming:
            async for chunk in handler(*args, **kwargs):
                yield JSONRPCResponse(id=custom_req.id, result=chunk)
            yield JSONRPCResponse(id=custom_req.id, result=None)  # EOS sentinel
        else:
            result = await handler(*args, **kwargs)
            yield JSONRPCResponse(id=custom_req.id, result=result)
    except Exception as e:
        yield JSONRPCResponse(id=custom_req.id, error=InternalError(message=str(e)))

    return
