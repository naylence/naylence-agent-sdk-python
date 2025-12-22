"""
Factory for creating AgentHttpGatewayListener instances.

This factory creates HTTP gateway listeners that expose agent RPC and messaging
endpoints over HTTP.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from naylence.fame.connector.transport_listener import TransportListener
from naylence.fame.connector.transport_listener_config import TransportListenerConfig
from naylence.fame.connector.transport_listener_factory import TransportListenerFactory
from naylence.fame.factory import create_resource
from naylence.fame.security.auth.authorizer_factory import AuthorizerFactory
from naylence.fame.util.logging import getLogger

from .agent_http_gateway_listener import AgentHttpGatewayListener, GatewayLimits

logger = getLogger(__name__)


class GatewayLimitsConfig(BaseModel):
    """Configuration for gateway structural limits."""

    max_method_length: Optional[int] = Field(
        default=None,
        alias="maxMethodLength",
        description="Maximum length of the method field (default: 256)",
    )
    max_target_addr_length: Optional[int] = Field(
        default=None,
        alias="maxTargetAddrLength",
        description="Maximum length of the targetAddr field (default: 512)",
    )
    max_type_length: Optional[int] = Field(
        default=None,
        alias="maxTypeLength",
        description="Maximum length of the type field for messages (default: 256)",
    )
    max_capabilities: Optional[int] = Field(
        default=None,
        alias="maxCapabilities",
        description="Maximum number of capabilities in the array (default: 16)",
    )
    max_capability_length: Optional[int] = Field(
        default=None,
        alias="maxCapabilityLength",
        description="Maximum length of each capability string (default: 256)",
    )
    body_limit_bytes: Optional[int] = Field(
        default=None,
        alias="bodyLimitBytes",
        description="Maximum request body size in bytes (default: 1MB)",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class AgentHttpGatewayListenerConfig(TransportListenerConfig):
    """Configuration for AgentHttpGatewayListener."""

    type: str = "AgentHttpGatewayListener"
    base_path: Optional[str] = Field(
        default="/fame/v1/gateway",
        alias="basePath",
        description="Base path for gateway endpoints",
    )
    limits: Optional[GatewayLimitsConfig] = Field(
        default=None,
        description="Structural limits for routing/envelope fields",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class AgentHttpGatewayListenerFactory(TransportListenerFactory):
    """
    Factory for creating AgentHttpGatewayListener instances.

    This factory creates HTTP gateway listeners that expose:
    - /rpc - Synchronous RPC invocations
    - /messages - Asynchronous message delivery
    - /health - Health checks
    """

    type: str = "AgentHttpGatewayListener"
    is_default: bool = False
    priority: int = 1000

    async def create(
        self,
        config: Optional[AgentHttpGatewayListenerConfig | dict[str, Any]] = None,
        **kwargs: Any,
    ) -> TransportListener:
        """
        Create an AgentHttpGatewayListener instance.

        Args:
            config: Listener configuration
            **kwargs: Additional creation parameters

        Returns:
            AgentHttpGatewayListener instance
        """
        # Lazy import to avoid loading dependencies unless actually creating an instance
        from naylence.fame.connector.default_http_server import DefaultHttpServer

        # Normalize configuration
        normalized = self._normalize_config(config)

        # Get or create the shared HTTP server
        http_server = await DefaultHttpServer.get_or_create(
            host=normalized.host,
            port=normalized.port,
        )

        # Create authorizer if configured
        authorizer = None
        if normalized.authorizer:
            authorizer = await create_resource(AuthorizerFactory, normalized.authorizer)

        # Build limits if configured
        limits = None
        if normalized.limits:
            limits = GatewayLimits(
                max_method_length=normalized.limits.max_method_length or 256,
                max_target_addr_length=normalized.limits.max_target_addr_length or 512,
                max_type_length=normalized.limits.max_type_length or 256,
                max_capabilities=normalized.limits.max_capabilities or 16,
                max_capability_length=normalized.limits.max_capability_length or 256,
                body_limit_bytes=normalized.limits.body_limit_bytes or 1_048_576,
            )

        listener = AgentHttpGatewayListener(
            http_server=http_server,
            base_path=normalized.base_path,
            authorizer=authorizer,
            limits=limits,
        )

        logger.debug(
            "agent_http_gateway_listener_created",
            host=normalized.host,
            port=normalized.port,
            base_path=normalized.base_path,
        )

        return listener

    def _normalize_config(
        self, config: Optional[AgentHttpGatewayListenerConfig | dict[str, Any]]
    ) -> AgentHttpGatewayListenerConfig:
        """Normalize configuration to AgentHttpGatewayListenerConfig."""
        if config is None:
            return AgentHttpGatewayListenerConfig()

        if isinstance(config, AgentHttpGatewayListenerConfig):
            return config

        if isinstance(config, dict):
            return AgentHttpGatewayListenerConfig(**config)

        # If it's another type of config, try to convert
        return AgentHttpGatewayListenerConfig(**config.model_dump())
