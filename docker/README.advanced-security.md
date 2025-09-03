# Naylence Agent SDK – Advanced Security Image

This Docker image contains the **Naylence Agent SDK** with **advanced security extensions** for building and running secure, zero-trust agents on the Naylence Agentic Fabric.

## What's Included

This image bundles:
- **naylence-agent-sdk** (Apache-2.0 licensed) - Core SDK components
- **naylence-advanced-security** (BSL-1.1 licensed) - Advanced security extensions

## Licensing

⚠️ **Important Licensing Information**

This image contains components under different licenses:
- **naylence-agent-sdk**: Licensed under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)
- **naylence-advanced-security**: Licensed under [Business Source License (BSL-1.1)](https://mariadb.com/bsl11/)

By using this image, you agree to comply with the terms of both licenses. Please review the license terms before use in production environments.

## Quick Start

Pull and run the image:

```bash
docker pull naylence/agent-sdk-adv-python:latest
docker run --rm naylence/agent-sdk-adv-python:latest python --version
```

## Available Tags

- `:latest` - Latest stable release
- `:X.Y.Z` - Specific version (e.g., `:0.1.20`)
- `:X.Y` - Minor version (e.g., `:0.1`)
- `:X` - Major version (e.g., `:0`)

Tags are aligned with the naylence-agent-sdk version.

## Usage Example

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
        agent_address = await fabric.serve(EchoAgent())
        remote_agent = Agent.remote_by_address(agent_address)
        result = await remote_agent.run_task(payload="Hello, World!")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Differences from OSS Image

If you only need the open-source components, use `naylence/agent-sdk-python` instead. This advanced image includes additional security features that require BSL licensing.

## Build Information

- **Base Image**: `python:3.12-slim`
- **Architecture**: `linux/amd64`, `linux/arm64`
- **Dockerfile**: [`docker/Dockerfile.advanced-security`](https://github.com/naylence/naylence-agent-sdk-python/blob/main/docker/Dockerfile.advanced-security)
- **Source**: [naylence/naylence-agent-sdk-python](https://github.com/naylence/naylence-agent-sdk-python)

## Support

- [GitHub Issues](https://github.com/naylence/naylence-agent-sdk-python/issues)
- [Documentation](https://github.com/naylence/naylence-agent-sdk-python#readme)
- [Examples](https://github.com/naylence/naylence-examples-python)

## Related Images

- **OSS-only image**: `naylence/agent-sdk-python`
- **Examples**: See [naylence-examples](https://github.com/naylence/naylence-examples-python) repository
