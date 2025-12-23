# Agent HTTP Gateway Example

This example runs a single Sentinel node with the Agent HTTP Gateway listener plus a tiny math agent.

## Prerequisites

- Install the package in development mode: `pip install -e .`
- Ensure the runtime dependencies are installed (fastapi, uvicorn, etc.)

## Run

From the `naylence-agent-sdk-python` directory:

```bash
python -m examples.gateway.main
```

Or from the `examples/gateway` directory:

```bash
FAME_LISTENER_AGENT_HTTP_GATEWAY_ENABLED=true python main.py
```

Environment variables:
- `FAME_NODE_ID` – Node ID for the sentinel.
- `FAME_PUBLIC_URL` – Public URL used in logs; defaults to `http://localhost:8080`.
- `FAME_SECURITY_PROFILE` – e.g. `open` (default).

## Gateway Endpoints

The gateway exposes:
- `POST /fame/v1/gateway/rpc` – Synchronous RPC invocations
- `POST /fame/v1/gateway/messages` – Asynchronous message delivery
- `GET /fame/v1/gateway/health` – Health check

## Example Requests

### RPC - Add two numbers
```bash
curl -X POST http://localhost:8080/fame/v1/gateway/rpc \
  -H "Content-Type: application/json" \
  -d '{"targetAddr": "math@fame.fabric", "method": "add", "params": {"x": 5, "y": 3}}'
```

### RPC - Multiply two numbers
```bash
curl -X POST http://localhost:8080/fame/v1/gateway/rpc \
  -H "Content-Type: application/json" \
  -d '{"targetAddr": "math@fame.fabric", "method": "multiply", "params": {"x": 4, "y": 7}}'
```

### Health Check
```bash
curl http://localhost:8080/fame/v1/gateway/health
```

## The Math Agent

The example includes a `MathAgent` bound at `math@fame.fabric` that provides:
- `add(x, y)` – Returns x + y
- `multiply(x, y)` – Returns x * y
- `fib_stream(n)` – Streams the first n Fibonacci numbers
