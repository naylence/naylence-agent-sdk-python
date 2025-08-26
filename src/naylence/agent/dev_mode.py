import asyncio
from typing import Any


SENTINEL_PORT = 8000

PROTO_MAJOR = 1
BASE_WS_URL = f"ws://localhost:{SENTINEL_PORT}/fame/v{PROTO_MAJOR}/attach/ws/downstream"

security_manager_config = {
    "type": "DefaultNodeSecurityManager",
    "security_policy": {
        "type": "DefaultSecurityPolicy",
        "signing": {
            "signing_material": "raw-key",
            # "require_cert_sid_match": True,
        },
    },
}

no_security_manager_config = {
    "type": "NoSecurityManager",
}

enabled_security_manager_config = no_security_manager_config

CLIENT_CONFIG = {
    "node": {
        "mode": "dev",
        "direct_parent_url": BASE_WS_URL,
        "security": enabled_security_manager_config,
    }
}

AGENT_CONFIG = {
    "node": {
        "mode": "dev",
        "direct_parent_url": BASE_WS_URL,
        "requested_logicals": ["fame.fabric"],
        "security": enabled_security_manager_config,
    }
}

SENTINEL_CONFIG = {
    "node": {
        "type": "Sentinel",
        "listeners": [
            {
                "type": "HttpListener",
                "port": SENTINEL_PORT,
            },
            {
                "type": "WebSocketListener",
                "port": SENTINEL_PORT,
            },
        ],
        "mode": "dev",
        "requested_logicals": ["fame.fabric"],
        "authorizer": {"type": "NoopAuthorizer"},
        "security": enabled_security_manager_config,
    },
}


def create_sentinel_app(*, config: Any = None, log_level: str | int = "info"):
    from fastapi import FastAPI
    from contextlib import asynccontextmanager
    from naylence.fame.core import FameFabric
    from naylence.fame.fastapi import create_websocket_attach_router
    from naylence.fame.util.logging import enable_logging
    from naylence.fame.fastapi.fame_context_middleware import (
        FameContextMiddleware,
        init_app_state,
    )

    enable_logging(log_level=log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with FameFabric.create(root_config=config or SENTINEL_CONFIG):
            init_app_state(app)
            app.include_router(create_websocket_attach_router())
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(FameContextMiddleware)

    return app


def run_sentinel_orig(
    *,
    config: Any = None,
    port: int | None = None,
    log_level: str | int = "info",
    **kwargs,
):
    import os
    import uvicorn

    app = create_sentinel_app(config=config, log_level=log_level)

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = port or int(os.getenv("APP_PORT", SENTINEL_PORT))

    uvicorn.run(app, host=host, port=port, log_level="error")


def run_sentinel(*, config: Any = None, log_level: str | int = "info", **kwargs):
    from naylence.fame.sentinel import Sentinel

    asyncio.run(
        Sentinel.aserve(
            root_config=config or SENTINEL_CONFIG, log_level=log_level, **kwargs
        )
    )
