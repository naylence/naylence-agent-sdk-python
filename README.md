[![Join our Discord](https://img.shields.io/badge/Discord-Join%20Chat-blue?logo=discord)](https://discord.gg/nwZAeqdv7y)

# Naylence Agent SDK (Python)

The **Naylence Agent SDK** is the official toolkit for building agents and clients on the Naylence Agentic Fabric. It gives you a clean, typed, async-first API for composing tasks, streaming results, and wiring agents together—locally or across a distributed fabric.

> If you're new to Naylence, start here. For lower‑level transport/fabric internals, see **naylence‑runtime**.

---

## Highlights

* **Ergonomic agent model** — subclass `BaseAgent` (one-shot) or `BackgroundTaskAgent` (long‑running/streaming) and focus on your logic.
* **Typed messages & tasks** — Pydantic models for `Task`, `Message`, `Artifact`, and JSON‑RPC A2A operations.
* **Async all the way** — non‑blocking lifecycle with easy scatter‑gather helpers (`Agent.broadcast`, `Agent.run_many`).
* **Remote proxies** — call agents by **address** or **capabilities** via `Agent.remote_*` helpers.
* **Streaming & cancellation** — subscribe to live status/artifacts; cancel in‑flight work.
* **FastAPI integration** — drop‐in JSON‑RPC router (`create_agent_router`) and `/agent.json` metadata endpoint.
* **Security ready** — works with runtime security profiles; **strict‑overlay** requires the `naylence‑advanced‑security` add‑on.

---

## Install

```bash
pip install naylence-agent-sdk
```

> Python **3.12+** is required.

---

## Quickstart (minimal)

```python
import asyncio
from typing import Any
from naylence.fame.core import FameFabric
from naylence.agent import Agent, BaseAgent

class EchoAgent(BaseAgent):
    async def run_task(self, payload: Any, id: Any) -> Any:
        return payload

async def main():
    async with FameFabric.create() as fabric:
        address = await fabric.serve(EchoAgent())
        echo = Agent.remote_by_address(address)
        print(await echo.run_task("Hello, world!", None))

asyncio.run(main())
```

For a gentle, runnable tour—from single‑process to distributed orchestration—use the **Examples** repo: [https://github.com/naylence/naylence-examples-python](https://github.com/naylence/naylence-examples-python).

---

## Core concepts

**Agents & tasks**

* Implement `run_task(payload, id)` for simple one‑shot work, or override `start_task(...)`/`get_task_status(...)` for background jobs.
* `Message.parts` carries either text (`TextPart`) or structured data (`DataPart`).
* Long‑running flows stream `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` until terminal (`COMPLETED`/`FAILED`/`CANCELED`).

**Remote proxies**

* `Agent.remote_by_address("echo@fame.fabric")` to call a known address.
* `Agent.remote_by_capabilities(["agent"])` to call by capability (fabric does resolution).

**Streaming & cancel**

* `subscribe_to_task_updates(...)` yields status/artifacts live.
* `cancel_task(...)` requests cooperative cancellation when supported by the agent.

**RPC operations**

* A2A JSON‑RPC methods (`tasks/send`, `.../get`, `.../cancel`, etc.) are provided for task lifecycle.
* Custom functions can be exposed via the RPC mixin in the underlying fabric (e.g., streaming operations).

**FastAPI router**

* Use `create_agent_router(agent)` to expose a JSON‑RPC endpoint (default: `/fame/v1/jsonrpc`) and `GET /agent.json` to return an `AgentCard`.

---

## Choosing an agent base class

* **`BaseAgent`** — great for synchronous/short tasks; the default fallback packages your return value into a `Task(COMPLETED)`.
* **`BackgroundTaskAgent`** — best for long‑running/streaming work. You implement `run_background_task(...)`; the base manages queues, TTLs, and end‑of‑stream.

Both base classes include sensible defaults (poll‑based streaming, simple auth pass‑through). You can override any part of the lifecycle.

---

## Development workflow

* Add your agents in a project with the SDK.
* Use `FameFabric.create()` in tests or local scripts to host agents in‑process.
* For distributed setups, operate a sentinel/fabric with **naylence‑runtime** (or your infra) and connect agents remotely.
* Use the **Examples** repo ([https://github.com/naylence/naylence-examples-python](https://github.com/naylence/naylence-examples-python)) to learn patterns like scatter‑gather, RPC streaming, cancellation, and security tiers.

---

## API Documentation

To generate API documentation from source:

```bash
# Generate Markdown docs to docs/api/
poetry run docs-gen

# Or specify a custom output directory
poetry run docs-gen --out path/to/output
```

The generated docs are Markdown files compatible with Nextra and other documentation systems.

---

## Security notes

The SDK runs on the Naylence fabric’s security profiles:

* **direct / gated / overlay** modes work out‑of‑the‑box with the open‑source stack.
* **strict‑overlay** (sealed overlay encryption + SPIFFE/X.509 identities) is available **only** with the **`naylence‑advanced‑security`** package.

See repo links below for the advanced add‑on and images that bundle it.

---

## Links

* **Agent SDK (this repo):** [https://github.com/naylence/naylence-agent-sdk-python](https://github.com/naylence/naylence-agent-sdk-python)
* **Examples (Python):** [https://github.com/naylence/naylence-examples-python](https://github.com/naylence/naylence-examples-python)
* **Runtime (fabric & transports):** [https://github.com/naylence/naylence-runtime-python](https://github.com/naylence/naylence-runtime-python)
* **Advanced Security add‑on:** [https://github.com/naylence/naylence-advanced-security-python](https://github.com/naylence/naylence-advanced-security-python)

Docker images:

* OSS: `naylence/agent-sdk-python`
* Advanced: `naylence/agent-sdk-adv-python` (includes `naylence-advanced-security`; BSL-licensed add-on)

---

## License & support

* **License:** Apache‑2.0 (SDK).&#x20;
* **Issues:** please use the appropriate GitHub repo (SDK, Runtime, Examples, Advanced Security).
