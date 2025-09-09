import asyncio
from typing import Any


SENTINEL_PORT = 8000


CLIENT_CONFIG = {
    "node": {
        "security": {
            "type": "SecurityProfile",
            "profile": "${env:FAME_SECURITY_PROFILE:open}",
        },
        "admission": {
            "type": "AdmissionProfile",
            "profile": "${env:FAME_ADMISSION_PROFILE:open}",
        },
        "storage": {
            "type": "StorageProfile",
            "profile": "${env:FAME_STORAGE_PROFILE:memory}",
        },
    }
}

NODE_CONFIG = {
    "node": {
        "type": "Node",
        "id": "${env:FAME_NODE_ID:}",
        "public_url": "${env:FAME_PUBLIC_URL:}",
        "requested_logicals": ["fame.fabric"],
        "security": {
            "type": "SecurityProfile",
            "profile": "${env:FAME_SECURITY_PROFILE:open}",
        },
        "admission": {
            "type": "AdmissionProfile",
            "profile": "${env:FAME_ADMISSION_PROFILE:open}",
        },
        "storage": {
            "type": "StorageProfile",
            "profile": "${env:FAME_STORAGE_PROFILE:memory}",
        },
    }
}

SENTINEL_CONFIG = {
    "node": {
        "type": "Sentinel",
        "id": "${env:FAME_NODE_ID:}",
        "public_url": "${env:FAME_PUBLIC_URL:}",
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
        "requested_logicals": ["fame.fabric"],
        "security": {
            "type": "SecurityProfile",
            "profile": "${env:FAME_SECURITY_PROFILE:open}",
        },
        "admission": {
            "type": "AdmissionProfile",
            "profile": "${env:FAME_ADMISSION_PROFILE:none}",
        },
        "storage": {
            "type": "StorageProfile",
            "profile": "${env:FAME_STORAGE_PROFILE:memory}",
        },
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


def run_sentinel(*, config: Any = None, log_level: str | int = "info", **kwargs):
    from naylence.fame.sentinel import Sentinel

    asyncio.run(
        Sentinel.aserve(
            root_config=config or SENTINEL_CONFIG, log_level=log_level, **kwargs
        )
    )
