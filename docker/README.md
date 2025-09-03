# Docker Images

This repository provides two Docker images for the Naylence Agent SDK:

## 1. Standard Image: `naylence/agent-sdk-python`

**License**: Apache-2.0  
**Includes**: 
- naylence-agent-sdk (Apache-2.0)
- All OSS dependencies

**Use when**: You only need the open-source SDK features.

```bash
docker pull naylence/agent-sdk-python:latest
```

## 2. Advanced Security Image: `naylence/agent-sdk-adv-python`

**License**: Apache-2.0 AND BSL-1.1  
**Includes**:
- naylence-agent-sdk (Apache-2.0)
- naylence-advanced-security (BSL-1.1)
- All dependencies

**Use when**: You need advanced security features and agree to BSL-1.1 terms.

```bash
docker pull naylence/agent-sdk-adv-python:latest
```

## Licensing Important Notes

⚠️ **The advanced security image contains components under the Business Source License (BSL-1.1)**

- Review the [BSL-1.1 license terms](https://mariadb.com/bsl11/) before using in production
- The BSL allows free use for development and non-production use cases
- Production use may require commercial licensing - see [naylence-advanced-security](https://github.com/naylence/naylence-advanced-security-python) repository for details

## Building Locally

### Standard Image
```bash
docker build -f docker/Dockerfile \
  --build-arg SDK_VERSION=0.1.20 \
  -t naylence/agent-sdk-python:local .
```

### Advanced Security Image
```bash
docker build -f docker/Dockerfile.advanced-security \
  --build-arg SDK_VERSION=0.1.20 \
  --build-arg ADVANCED_SECURITY_VERSION=0.1.11 \
  -t naylence/agent-sdk-adv-python:local .
```

## Testing

Both images include the same basic functionality. Test with:

```bash
# Standard image
docker run --rm naylence/agent-sdk-python:latest python --version

# Advanced security image  
docker run --rm naylence/agent-sdk-adv-python:latest python --version

# Run examples
docker run --rm -v $(pwd)/examples:/app/examples \
  naylence/agent-sdk-adv-python:latest \
  python examples/quickstart/hello.py
```

## CI/CD

- Standard image: Built by `.github/workflows/publish-docker.yml`
- Advanced security image: Built by `.github/workflows/publish-docker-advanced.yml`

Both workflows are triggered by:
- Git tags (`v*`)
- GitHub releases
- Successful PyPI package publication
- Manual workflow dispatch
