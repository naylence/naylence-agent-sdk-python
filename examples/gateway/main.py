"""
Agent HTTP Gateway Example - Main entry point.

This example demonstrates running a Sentinel node with the Agent HTTP Gateway
listener and a simple MathAgent.
"""

import asyncio
import signal
import sys

from naylence.fame.core import FameFabric
from naylence.fame.util.logging import enable_logging
from naylence.agent.configs import SENTINEL_CONFIG

from common import AGENT_ADDR
from math_agent import MathAgent


async def main() -> None:
    """Run the gateway example."""
    # Enable logging for better visibility
    enable_logging(log_level="info")

    print(f"Starting gateway with agent at {AGENT_ADDR}...")

    async with FameFabric.create(root_config=SENTINEL_CONFIG) as fabric:
        # Create and serve the math agent
        agent = MathAgent()
        agent_address = await fabric.serve(agent, service_name=AGENT_ADDR)

        print(f"MathAgent serving at: {agent_address}")
        print("Gateway endpoints available:")
        print("  POST /fame/v1/gateway/rpc")
        print("  POST /fame/v1/gateway/messages")
        print("  GET  /fame/v1/gateway/health")
        print()
        print("Example curl commands:")
        print('  curl -X POST http://localhost:8080/fame/v1/gateway/rpc \\')
        print('    -H "Content-Type: application/json" \\')
        print(
            "    -d '{\"targetAddr\": \"math@fame.fabric\", "
            "\"method\": \"add\", \"params\": {\"x\": 5, \"y\": 3}}'"
        )
        print()
        print("Press Ctrl+C to stop...")

        # Keep the process alive until interrupted
        stop_event = asyncio.Event()

        def handle_signal(signum, frame):
            print("\nShutting down...")
            stop_event.set()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        await stop_event.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"[gateway] failed to start: {e}", file=sys.stderr)
        sys.exit(1)
