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
        "delivery": {
            "type": "DeliveryProfile",
            "profile": "${env:FAME_DELIVERY_PROFILE:at-most-once}",
        },
    },
}
