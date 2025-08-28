FROM python:3.12-slim

# Only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Environment hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install package (will fail if compilation needed)
ARG SDK_VERSION
RUN pip install --no-cache-dir \
  --index-url https://test.pypi.org/simple \
  --extra-index-url https://pypi.org/simple \
  naylence-agent-sdk${SDK_VERSION:+==${SDK_VERSION}}

# Non-root user
RUN useradd -m agent
USER agent

CMD ["python", "--version"]