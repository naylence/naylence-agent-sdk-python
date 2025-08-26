from fastapi import APIRouter
from fastapi.responses import JSONResponse

from naylence.agent.a2a_types import (
    A2ARequest,
    InternalError,
    InvalidParamsError,
    InvalidRequestError,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MethodNotFoundError,
)
from naylence.agent.agent import Agent
from naylence.agent.errors import (
    AgentException,
    AuthorizationException,
    ConflictException,
    InvalidDataException,
    InvalidTaskException,
    NoDataFoundException,
    RateLimitExceededException,
    UnsupportedOperationException,
)


PROTO_MAJOR = 1
DEFAULT_PREFIX = f"/fame/v{PROTO_MAJOR}/jsonrpc"


def create_agent_router(agent: Agent, prefix: str = DEFAULT_PREFIX) -> APIRouter:
    router = APIRouter(prefix=prefix)

    @router.post(
        "",
        response_model=JSONRPCResponse,
        response_model_exclude_none=True,
        summary="JSON-RPC A2A Handler",
        description="Handles JSON-RPC requests for A2A agent methods.",
    )
    async def handle_rpc(rpc_request: JSONRPCRequest) -> JSONRPCResponse:
        try:
            parsed: JSONRPCRequest = A2ARequest.validate_python(
                rpc_request.model_dump(by_alias=True)
            )
        except Exception as e:
            return JSONRPCResponse(id=None, error=InvalidRequestError(data=str(e)))

        method = parsed.method
        params = parsed.params

        try:
            match method:
                case "tasks/send":
                    result = await agent.start_task(params)
                    return JSONRPCResponse(
                        id=parsed.id, result=result.model_dump(by_alias=True)
                    )
                case "tasks/get":
                    result = await agent.get_task_status(params)
                    return JSONRPCResponse(
                        id=parsed.id, result=result.model_dump(by_alias=True)
                    )
                case "tasks/cancel":
                    result = await agent.cancel_task(params)
                    return JSONRPCResponse(
                        id=parsed.id, result=result.model_dump(by_alias=True)
                    )
                case "tasks/pushNotification/set":
                    result = await agent.register_push_endpoint(params)
                    return JSONRPCResponse(
                        id=parsed.id, result=result.model_dump(by_alias=True)
                    )
                case "tasks/pushNotification/get":
                    result = await agent.get_push_notification_config(params)
                    return JSONRPCResponse(
                        id=parsed.id, result=result.model_dump(by_alias=True)
                    )
                case "agent.get_card":
                    result = await agent.get_agent_card()
                    return JSONRPCResponse(
                        id=parsed.id, result=result.model_dump(by_alias=True)
                    )
                case _:
                    return JSONRPCResponse(id=parsed.id, error=MethodNotFoundError())

        except InvalidTaskException as e:
            return JSONRPCResponse(id=parsed.id, error=InvalidParamsError(data=str(e)))
        except InvalidDataException as e:
            return JSONRPCResponse(id=parsed.id, error=InvalidParamsError(data=str(e)))
        except NoDataFoundException as e:
            return JSONRPCResponse(id=parsed.id, error=InvalidParamsError(data=str(e)))
        except ConflictException as e:
            return JSONRPCResponse(id=parsed.id, error=InvalidParamsError(data=str(e)))
        except UnsupportedOperationException as e:
            return JSONRPCResponse(
                id=parsed.id,
                error=JSONRPCError(
                    code=-32004, message="Unsupported operation", data=str(e)
                ),
            )
        except AuthorizationException as e:
            return JSONRPCResponse(
                id=parsed.id,
                error=JSONRPCError(code=-32600, message="Unauthorized", data=str(e)),
            )
        except RateLimitExceededException as e:
            return JSONRPCResponse(
                id=parsed.id,
                error=JSONRPCError(
                    code=-32029, message="Rate limit exceeded", data=str(e)
                ),
            )
        except AgentException as e:
            return JSONRPCResponse(id=parsed.id, error=InternalError(data=str(e)))
        except Exception as e:
            return JSONRPCResponse(id=parsed.id, error=InternalError(data=str(e)))

    @router.get("/agent.json")
    async def get_agent_card():
        card = await agent.get_agent_card()
        return JSONResponse(content=card.model_dump(by_alias=True))

    return router
