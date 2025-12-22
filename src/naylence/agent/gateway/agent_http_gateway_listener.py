"""
Agent HTTP Gateway Listener for exposing agent RPC and message endpoints.

This module provides an HTTP listener that exposes gateway endpoints for:
- RPC requests (POST /rpc)
- Message delivery (POST /messages)
- Health checks (GET /health)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from naylence.fame.connector.transport_listener import TransportListener
from naylence.fame.core import (
    AuthorizationContext,
    FameAddress,
    FameDeliveryContext,
    FameResponseType,
    SecurityContext,
)
from naylence.fame.errors import BackPressureFull
from naylence.fame.node.node_event_listener import NodeEventListener
from naylence.fame.security.auth.authorizer import Authorizer
from naylence.fame.util.logging import getLogger

if TYPE_CHECKING:
    from naylence.fame.connector.http_server import HttpServer
    from naylence.fame.node.node_like import NodeLike

logger = getLogger(__name__)

# Constants
DEFAULT_BASE_PATH = "/fame/v1/gateway"
DEFAULT_TIMEOUT_MS = 30_000
MAX_TIMEOUT_MS = 120_000

# Structural limits for routing/envelope fields (not payload content)
DEFAULT_MAX_METHOD_LENGTH = 256
DEFAULT_MAX_TARGET_ADDR_LENGTH = 512
DEFAULT_MAX_TYPE_LENGTH = 256
DEFAULT_MAX_CAPABILITIES = 16
DEFAULT_MAX_CAPABILITY_LENGTH = 256
DEFAULT_BODY_LIMIT_BYTES = 1_048_576  # 1MB


@dataclass
class GatewayLimits:
    """
    Structural limits for gateway request fields.
    These protect against abuse in routing/envelope fields, not payload content.
    """

    max_method_length: int = DEFAULT_MAX_METHOD_LENGTH
    max_target_addr_length: int = DEFAULT_MAX_TARGET_ADDR_LENGTH
    max_type_length: int = DEFAULT_MAX_TYPE_LENGTH
    max_capabilities: int = DEFAULT_MAX_CAPABILITIES
    max_capability_length: int = DEFAULT_MAX_CAPABILITY_LENGTH
    body_limit_bytes: int = DEFAULT_BODY_LIMIT_BYTES


@dataclass
class RpcRequest:
    """Parsed RPC request."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    timeout_ms: Optional[int] = None
    target_addr: Optional[str] = None
    capabilities: Optional[list[str]] = None


@dataclass
class MessageRequest:
    """Parsed message request."""

    target_addr: Optional[str] = None
    capabilities: Optional[list[str]] = None
    type: Optional[str] = None
    payload: Any = None


class AgentHttpGatewayListener(TransportListener, NodeEventListener):
    """
    HTTP listener that provides gateway endpoints for agent RPC and messaging.

    This listener creates HTTP routes for:
    - /rpc - Synchronous RPC invocations
    - /messages - Asynchronous message delivery
    - /health - Health checks
    """

    def __init__(
        self,
        *,
        http_server: HttpServer,
        base_path: Optional[str] = None,
        authorizer: Optional[Authorizer] = None,
        limits: Optional[GatewayLimits] = None,
    ):
        self._http_server = http_server
        self._authorizer = authorizer
        self._base_path = self._sanitize_base_path(base_path)
        self._limits = self._normalize_limits(limits)
        self._node: Optional[NodeLike] = None
        self._router_registered = False

    @property
    def http_server(self) -> HttpServer:
        """Get the HTTP server instance."""
        return self._http_server

    @property
    def priority(self) -> int:
        """Event listener priority."""
        return 1000

    # ── NodeEventListener interface ─────────────────────────────────────────

    async def on_node_initialized(self, node: NodeLike) -> None:
        """Register routes with the HTTP server when node is initialized."""
        if self._router_registered:
            return

        self._node = node

        logger.debug(
            "registering_gateway_routes",
            class_name=self.__class__.__name__,
            base_path=self._base_path,
        )

        router = await self._create_router()
        self._http_server.include_router(router)
        self._router_registered = True

        logger.debug(
            "gateway_routes_registered",
            base_url=self._http_server.actual_base_url,
            base_path=self._base_path,
        )

    async def on_node_started(self, node: NodeLike) -> None:
        """Start the HTTP server if not already running."""
        if self._http_server.is_running:
            return
        await self._http_server.start()

    async def on_node_stopped(self, node: NodeLike) -> None:
        """Clean up when node stops."""
        self._router_registered = False
        self._node = None

        # Release the HTTP server reference
        from naylence.fame.connector.default_http_server import DefaultHttpServer

        if isinstance(self._http_server, DefaultHttpServer):
            try:
                await DefaultHttpServer.release(
                    host=self._http_server.host,
                    port=self._http_server.port,
                )
            except Exception:
                # Best-effort cleanup; ignore failures to avoid masking stop errors.
                pass

    # ── Router creation ──────────────────────────────────────────────────────

    async def _create_router(self) -> APIRouter:
        """Create the FastAPI router with gateway endpoints."""
        router = APIRouter(prefix=self._base_path)

        @router.post("/rpc")
        async def handle_rpc(request: Request) -> Response:
            return await self._handle_rpc(request)

        @router.post("/messages")
        async def handle_message(request: Request) -> Response:
            return await self._handle_message(request)

        @router.get("/health")
        async def health_check() -> dict[str, str]:
            return {
                "status": "healthy",
                "listenerType": "AgentHttpGatewayListener",
            }

        return router

    # ── Request handlers ─────────────────────────────────────────────────────

    async def _handle_rpc(self, request: Request) -> Response:
        """Handle RPC requests."""
        node = self._node
        if not node:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "error": "Node not initialized"},
            )

        try:
            body = await request.json()
            parsed = self._parse_rpc_request(body)
            if not parsed:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "error": "Invalid RPC request body"},
                )

            authorization = await self._authenticate_request(
                request.headers.get("authorization")
            )
            logger.debug(
                "rpc_request_authenticated",
                has_authorization=bool(authorization),
                principal=authorization.principal if authorization else None,
                scopes=authorization.granted_scopes if authorization else [],
            )

            timeout_ms = self._normalize_timeout(parsed.timeout_ms)
            result = await self._invoke_rpc(node, parsed, timeout_ms)

            return JSONResponse(
                status_code=200,
                content={"ok": True, "result": result},
            )

        except Exception as error:
            mapped = self._map_error(error)
            content: dict[str, Any] = {"ok": False, "error": mapped["message"]}
            if mapped.get("code"):
                content["code"] = mapped["code"]
            return JSONResponse(status_code=mapped["status"], content=content)

    async def _handle_message(self, request: Request) -> Response:
        """Handle message requests."""
        node = self._node
        if not node:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "error": "Node not initialized"},
            )

        try:
            body = await request.json()
            parsed = self._parse_message_request(body)
            if not parsed:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "error": "Invalid message request body"},
                )

            authorization = await self._authenticate_request(
                request.headers.get("authorization")
            )
            logger.debug(
                "message_request_authenticated",
                has_authorization=bool(authorization),
                principal=authorization.principal if authorization else None,
                scopes=authorization.granted_scopes if authorization else [],
            )

            await self._send_message(node, parsed, authorization)

            return JSONResponse(
                status_code=202,
                content={"status": "message_accepted"},
            )

        except Exception as error:
            mapped = self._map_error(error)
            content: dict[str, Any] = {"ok": False, "error": mapped["message"]}
            if mapped.get("code"):
                content["code"] = mapped["code"]
            return JSONResponse(status_code=mapped["status"], content=content)

    # ── Request parsing ──────────────────────────────────────────────────────

    def _parse_rpc_request(self, body: Any) -> Optional[RpcRequest]:
        """Parse and validate RPC request body."""
        if not isinstance(body, dict):
            return None

        method = body.get("method", "")
        if not isinstance(method, str):
            return None
        method = method.strip()
        if not method:
            return None

        # Validate structural limits
        if len(method) > self._limits.max_method_length:
            return None

        timeout_ms = self._parse_timeout_value(body.get("timeoutMs"))

        params_raw = body.get("params")
        params = params_raw if isinstance(params_raw, dict) else {}

        target_addr_raw = body.get("targetAddr", "")
        target_addr = target_addr_raw.strip() if isinstance(target_addr_raw, str) else ""
        if len(target_addr) > self._limits.max_target_addr_length:
            return None

        capabilities_raw = body.get("capabilities", [])
        capabilities: list[str] = []
        if isinstance(capabilities_raw, list):
            for cap in capabilities_raw:
                if isinstance(cap, str):
                    cap_stripped = cap.strip()
                    if cap_stripped:
                        capabilities.append(cap_stripped)

        # Validate capabilities limits
        if len(capabilities) > self._limits.max_capabilities:
            return None
        for cap in capabilities:
            if len(cap) > self._limits.max_capability_length:
                return None

        if target_addr:
            return RpcRequest(
                method=method,
                params=params,
                timeout_ms=timeout_ms,
                target_addr=target_addr,
            )

        if capabilities:
            return RpcRequest(
                method=method,
                params=params,
                timeout_ms=timeout_ms,
                capabilities=capabilities,
            )

        return None

    def _parse_message_request(self, body: Any) -> Optional[MessageRequest]:
        """Parse and validate message request body."""
        if not isinstance(body, dict):
            return None

        target_addr_raw = body.get("targetAddr", "")
        target_addr = target_addr_raw.strip() if isinstance(target_addr_raw, str) else ""

        # Validate targetAddr limit
        if len(target_addr) > self._limits.max_target_addr_length:
            return None

        capabilities_raw = body.get("capabilities", [])
        capabilities: list[str] = []
        if isinstance(capabilities_raw, list):
            for cap in capabilities_raw:
                if isinstance(cap, str):
                    cap_stripped = cap.strip()
                    if cap_stripped:
                        capabilities.append(cap_stripped)

        # Validate capabilities limits
        if len(capabilities) > self._limits.max_capabilities:
            return None
        for cap in capabilities:
            if len(cap) > self._limits.max_capability_length:
                return None

        type_raw = body.get("type", "")
        type_str = type_raw.strip() if isinstance(type_raw, str) else ""

        # Validate type limit
        if len(type_str) > self._limits.max_type_length:
            return None

        payload = body.get("payload")

        if not type_str and payload is None:
            return None

        if target_addr:
            return MessageRequest(
                target_addr=target_addr,
                type=type_str if type_str else None,
                payload=payload,
            )

        if capabilities:
            return MessageRequest(
                capabilities=capabilities,
                type=type_str if type_str else None,
                payload=payload,
            )

        return None

    def _parse_timeout_value(self, value: Any) -> Optional[int]:
        """Parse timeout value from request."""
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value == value:  # not NaN
            return int(value)
        if isinstance(value, str):
            value_stripped = value.strip()
            if value_stripped:
                try:
                    return int(value_stripped)
                except ValueError:
                    pass
        return None

    def _normalize_timeout(self, value: Optional[int]) -> int:
        """Normalize timeout value to valid range."""
        if value is None or value <= 0:
            return DEFAULT_TIMEOUT_MS
        return min(value, MAX_TIMEOUT_MS)

    # ── RPC and message invocation ───────────────────────────────────────────

    async def _invoke_rpc(
        self, node: NodeLike, request: RpcRequest, timeout_ms: int
    ) -> Any:
        """Invoke RPC method on the node."""
        timeout = self._normalize_timeout(timeout_ms)
        # Wrap params in the structure expected by RpcMixin.handle_rpc_request
        # which extracts kwargs from params.get("kwargs", {})
        rpc_params = {"kwargs": request.params} if request.params else {}
        if request.target_addr:
            return await node.invoke(
                FameAddress(request.target_addr),
                request.method,
                rpc_params,
                timeout,
            )
        if request.capabilities:
            return await node.invoke_by_capability(
                request.capabilities,
                request.method,
                rpc_params,
                timeout,
            )
        raise ValueError("No target_addr or capabilities specified")

    async def _send_message(
        self,
        node: NodeLike,
        request: MessageRequest,
        authorization: Optional[AuthorizationContext],
    ) -> None:
        """Send a message through the node."""
        # Build the envelope payload
        frame_payload: dict[str, Any] = {}
        if request.type:
            frame_payload["type"] = request.type
        if request.payload is not None:
            frame_payload["payload"] = request.payload

        # Create envelope options
        envelope_options: dict[str, Any] = {
            "frame": {
                "type": "Data",
                "payload": frame_payload,
            },
            "response_type": FameResponseType.NONE,
        }

        if request.target_addr:
            envelope_options["to"] = request.target_addr
        elif request.capabilities:
            envelope_options["capabilities"] = request.capabilities

        envelope = node.envelope_factory.create_envelope(**envelope_options)
        # Create delivery context with authorization if provided
        security = SecurityContext(authorization=authorization) if authorization else None
        context = FameDeliveryContext(security=security)
        await node.send(envelope, context)

    # ── Authentication ───────────────────────────────────────────────────────

    async def _authenticate_request(
        self, header: Optional[str]
    ) -> Optional[AuthorizationContext]:
        """Authenticate request using the authorizer."""
        authorizer = await self._resolve_authorizer()
        if not authorizer:
            return None

        token = header or ""
        try:
            result = await authorizer.authenticate(token)
            if not result:
                raise ValueError("Authentication failed")
            return result
        except Exception as error:
            if isinstance(error, Exception):
                raise
            raise ValueError(str(error)) from error

    async def _resolve_authorizer(self) -> Optional[Authorizer]:
        """Resolve the authorizer to use for authentication."""
        if self._authorizer:
            return self._authorizer

        node = self._node
        if not node:
            return None

        security_manager = node.security_manager
        if not security_manager:
            return None

        return security_manager.authorizer

    # ── Error mapping ────────────────────────────────────────────────────────

    def _map_error(self, error: Any) -> dict[str, Any]:
        """Map exception to HTTP status code and message."""
        # Check for back pressure / queue full error
        if isinstance(error, BackPressureFull):
            return {"status": 429, "message": "receiver busy", "code": "queue_full"}

        if isinstance(error, Exception):
            message = str(error) or "Internal server error"
            normalized = message.lower()

            if "authentication failed" in normalized:
                return {"status": 401, "message": message, "code": "unauthorized"}
            if "forbidden" in normalized or "not authorized" in normalized:
                return {"status": 403, "message": message, "code": "forbidden"}
            if "timeout" in normalized:
                return {"status": 504, "message": message, "code": "timeout"}
            if "no route" in normalized or "no local handler" in normalized:
                return {"status": 404, "message": message, "code": "not_found"}
            if "invalid" in normalized:
                return {"status": 400, "message": message, "code": "invalid_request"}

            return {"status": 500, "message": message}

        return {"status": 500, "message": "Internal server error"}

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_base_path(base_path: Optional[str]) -> str:
        """Sanitize and normalize base path."""
        if not base_path or not isinstance(base_path, str):
            return DEFAULT_BASE_PATH
        trimmed = base_path.strip()
        if not trimmed:
            return DEFAULT_BASE_PATH
        if not trimmed.startswith("/"):
            return f"/{trimmed}"
        return trimmed

    @staticmethod
    def _normalize_limits(limits: Optional[GatewayLimits]) -> GatewayLimits:
        """Normalize limits with defaults."""
        if limits is None:
            return GatewayLimits()
        return limits

    @staticmethod
    def _positive_int_or_default(value: Optional[int], default: int) -> int:
        """Return positive integer or default."""
        if isinstance(value, int) and value > 0:
            return value
        return default
