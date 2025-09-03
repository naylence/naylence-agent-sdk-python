# Naylence Agent SDK

The **Naylence Agent SDK** is the official developer toolkit for building and running agents on top of the [Naylence Agentic Fabric](https://github.com/naylence).

It provides the core runtime, APIs, and developer tools to create **secure, durable, zero-trust agents** that can interoperate across domains.

---

## Features

* ⚡ **Simple developer experience** – clean APIs and idioms for agent construction.
* 🧩 **Extensible by design** – plug in your own Authorizers, Security Managers, Connectors, etc.
* 🔒 **Zero-trust security** – built-in support for overlay encryption, envelope signing, and SPIFFE-style identities.
* 🌐 **Federated messaging** – agents can communicate across sentinels, domains, and organizations.
* 🐳 **Container-ready** – official Docker images (`naylence/agent-sdk-python` for OSS, `naylence/agent-sdk-adv-python` for advanced security) for rapid prototyping and deployment.
* 📦 **Typed and structured** – Python 3.12+, [Pydantic](https://docs.pydantic.dev/) models for safe envelopes and configs.

---

## Installation

Install directly from PyPI:

```bash
pip install naylence-agent-sdk
```

or with Poetry:

```bash
poetry add naylence-agent-sdk
```

---

## Quickstart

```python
import asyncio
from typing import Any

from naylence.fame.core import FameFabric

from naylence.agent import Agent, BaseAgent


class EchoAgent(BaseAgent):
    async def run_task(self, payload: Any, id: Any) -> Any:
        return payload


async def main():
    # --- Start a FameFabric session and serve the agent ---
    async with FameFabric.create() as fabric:
        # Register the SimpleAgent with the fabric and get its address.
        # In real deployments, this would happen in the agent runtime process.
        agent_address = await fabric.serve(EchoAgent())

        # Resolve a remote proxy to the agent.
        # This simulates a client or external caller invoking the agent.
        remote_agent = Agent.remote_by_address(agent_address)

        # Send a new task to the remote agent.
        result = await remote_agent.run_task(payload="Hello, World!")
        print(result)


# Entry point for running this script directly.
if __name__ == "__main__":
    asyncio.run(main())
```

Run with:

```bash
python echo_agent.py
```

---

## Examples

* A **minimal quickstart** is included in this repo under [`examples/quickstart`](./examples/quickstart).
* A full gallery of **docker-compose examples** lives in the [naylence-examples repo](https://github.com/naylence/naylence-examples).

These examples demonstrate:

* Multi-agent orchestration
* Overlay security and sealed channels
* Federation across sentinels

---

## Development

Clone and set up Poetry:

```bash
git clone https://github.com/naylence/naylence-agent-sdk-python.git
cd naylence-agent-sdk
poetry install
```

Run tests:

```bash
poetry run pytest
```

Build the wheel:

```bash
poetry build
```

---

## License

Licensed under the [Apache 2.0 License](./LICENSE).
For advanced security extensions, see [Naylence Advanced Security](https://github.com/naylence/naylence-advanced-security).

---

## Links

* [Naylence core](https://github.com/naylence/naylence-core-python)
* [Naylence runtime](https://github.com/naylence/naylence-runtime-python)
* [Examples repo](https://github.com/naylence/naylence-examples-python)

---
