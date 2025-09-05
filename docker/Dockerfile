FROM python:3.12-slim

# Environment hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create non-root user first
RUN useradd -m -u 1000 agent

# Set up virtual environment
ENV VIRTUAL_ENV=/home/agent/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Change ownership of venv to agent user
RUN chown -R agent:agent $VIRTUAL_ENV

WORKDIR /app

# Switch to non-root user before pip install
USER agent

# Install package in virtual environment
ARG SDK_VERSION
RUN pip install --no-cache-dir \
  --index-url https://pypi.org/simple \
  --extra-index-url https://test.pypi.org/simple \
  naylence-agent-sdk${SDK_VERSION:+==${SDK_VERSION}}

CMD ["python", "--version"]