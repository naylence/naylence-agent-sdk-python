"""
Public API surface for documentation generation.

This module exports only the curated public API of the Naylence Agent SDK.
It is used by griffe2md to generate API reference documentation.

Usage:
    from naylence.agent.public_api import Agent, BaseAgent, BackgroundTaskAgent
"""

from naylence.agent.a2a_types import (
    Artifact,
    DataPart,
    FilePart,
    Message,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from naylence.agent.agent import Agent
from naylence.agent.agent_proxy import AgentProxy
from naylence.agent.background_task_agent import BackgroundTaskAgent
from naylence.agent.base_agent import BaseAgent, BaseAgentState
from naylence.agent.configs import (
    CLIENT_CONFIG,
    NODE_CONFIG,
    SENTINEL_CONFIG,
)
from naylence.agent.errors import (
    AgentException,
    AuthorizationException,
    ConflictException,
    DuplicateTaskException,
    InvalidDataException,
    InvalidTaskException,
    NoDataFoundException,
    PushNotificationNotSupportedException,
    RateLimitExceededException,
    TaskNotCancelableException,
    UnsupportedOperationException,
)
from naylence.agent.util import first_data_part, first_text_part, make_task

__all__ = [
    # Core Agent Classes
    "Agent",
    "AgentProxy",
    "BaseAgent",
    "BaseAgentState",
    "BackgroundTaskAgent",
    # A2A Types
    "Task",
    "TaskState",
    "TaskStatus",
    "Message",
    "Part",
    "TextPart",
    "DataPart",
    "FilePart",
    "Artifact",
    "TaskStatusUpdateEvent",
    "TaskArtifactUpdateEvent",
    # Configuration
    "NODE_CONFIG",
    "SENTINEL_CONFIG",
    "CLIENT_CONFIG",
    # Exceptions
    "AgentException",
    "AuthorizationException",
    "ConflictException",
    "DuplicateTaskException",
    "InvalidDataException",
    "InvalidTaskException",
    "NoDataFoundException",
    "PushNotificationNotSupportedException",
    "RateLimitExceededException",
    "TaskNotCancelableException",
    "UnsupportedOperationException",
    # Utilities
    "first_text_part",
    "first_data_part",
    "make_task",
]
