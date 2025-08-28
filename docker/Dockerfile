FROM python:3.12-slim AS base

# System deps (adjust if your SDK needs more)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libssl-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Environment hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Default: install from PyPI
# Override with build arg to pin SDK version
ARG SDK_VERSION
RUN pip install --no-cache-dir \
  --index-url https://test.pypi.org/simple \
  --extra-index-url https://pypi.org/simple \
  naylence-agent-sdk${SDK_VERSION:+==${SDK_VERSION}}

# # Non-root user
RUN useradd -m agent
USER agent

# # Entrypoint left open — consumers extend this image
CMD ["python", "--version"]
