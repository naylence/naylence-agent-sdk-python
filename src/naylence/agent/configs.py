from naylence.fame.factory import Expressions


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
        "identity_policy": {
            "type": "NodeIdentityPolicyProfile",
            "profile": "${env:FAME_NODE_IDENTITY_PROFILE:default}",
        },
        "storage": {
            "type": "StorageProfile",
            "profile": "${env:FAME_STORAGE_PROFILE:memory}",
        },
        "delivery": {
            "type": "DeliveryProfile",
            "profile": "${env:FAME_DELIVERY_PROFILE:at-most-once}",
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
        "identity_policy": {
            "type": "NodeIdentityPolicyProfile",
            "profile": "${env:FAME_NODE_IDENTITY_PROFILE:default}",
        },
        "storage": {
            "type": "StorageProfile",
            "profile": "${env:FAME_STORAGE_PROFILE:memory}",
        },
        "delivery": {
            "type": "DeliveryProfile",
            "profile": "${env:FAME_DELIVERY_PROFILE:at-most-once}",
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
                "port": Expressions.env('FAME_LISTENER_HTTP_PORT', \
                    Expressions.env('FAME_LISTENER_PORT', SENTINEL_PORT)),
                "enabled": "${env:FAME_LISTENER_HTTP_ENABLED:true}",
            },
            {
                "type": "WebSocketListener",
                "port": Expressions.env('FAME_LISTENER_WEBSOCKET_PORT', \
                    Expressions.env('FAME_LISTENER_PORT', SENTINEL_PORT)),
                "enabled": "${env:FAME_LISTENER_WEBSOCKET_ENABLED:true}",
            },
            {
                "type": "AgentHttpGatewayListener",
                "port": Expressions.env('FAME_LISTENER_AGENT_HTTP_GATEWAY_PORT', \
                    Expressions.env('FAME_LISTENER_PORT', SENTINEL_PORT)),
                "enabled": "${env:FAME_LISTENER_AGENT_HTTP_GATEWAY_ENABLED:false}",
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
        "identity_policy": {
            "type": "NodeIdentityPolicyProfile",
            "profile": "${env:FAME_NODE_IDENTITY_PROFILE:default}",
        },
        "storage": {
            "type": "StorageProfile",
            "profile": "${env:FAME_STORAGE_PROFILE:memory}",
        },
        "delivery": {
            "type": "DeliveryProfile",
            "profile": "${env:FAME_DELIVERY_PROFILE:at-most-once}",
        },
    },
}
