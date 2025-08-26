import base64
from typing import Any, List, Literal, Optional

from naylence.fame.core.protocol.frames import DataFrame

from naylence.agent.a2a_types import (
    DataPart,
    Message,
    Part,
    PushNotificationConfig,
    Task,
    TaskSendParams,
    TaskState,
    TaskStatus,
    TextPart,
)


def extract_id(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        return obj.get("id")
    return getattr(obj, "id", None)


def decode_fame_data_payload(frame: DataFrame) -> Any:
    if frame.codec == "b64":
        payload_bytes = base64.b64decode(frame.payload)
        return payload_bytes
    return frame.payload


def first_data_part(message: Optional[Message]) -> Optional[dict[str, Any]]:
    if not message:
        return None

    parts = message.parts
    if not parts:
        return None

    first = parts[0]
    if isinstance(first, DataPart):
        return first.data

    return None


def first_text_part(message: Optional[Message]) -> Optional[str]:
    """
    Safely extract the .text field from the first Part in a list, if it's a TextPart.

    Parameters:
      • parts: a sequence of Part (e.g. [TextPart, DataPart, …]).

    Returns:
      • The `text` string if the first part is a TextPart.
      • None if the list is empty or the first part is not a TextPart.

    Example:
        >>> msg_parts = [TextPart(type="text", text="Hello", metadata=None)]
        >>> first_text_part(msg_parts)
        "Hello"

        >>> no_parts: List[Part] = []
        >>> first_text_part(no_parts)  # returns None

        >>> mixed_parts = [DataPart(type="data", data={"x": 1}, metadata=None)]
        >>> first_text_part(mixed_parts)  # returns None
    """
    if not message:
        return None

    parts = message.parts
    if not parts:
        return None

    first = parts[0]
    if isinstance(first, TextPart):
        return first.text

    return None


def make_task_params(
    *,
    id: str,
    role: Literal["user", "agent"] = "agent",
    payload: dict[str, Any] | str | None = None,
    session_id: Optional[str] = None,
    accepted_output_modes: Optional[List[str]] = None,
    push_notification: Optional[PushNotificationConfig] = None,
    history_length: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> TaskSendParams:
    """
    Convenience builder for TaskSendParams.

    Parameters:
      • id                  - unique task ID.
      • role                - one of "user" or "agent" (defaults to "agent").
      • payload             - either a dict (becomes a DataPart) or a string (becomes a TextPart).
      • session_id          - optional sessionId (defaults to id if not provided).
      • accepted_output_modes - optional list of accepted output modes.
      • push_notification   - optional PushNotificationConfig.
      • history_length      - optional historyLength (int).
      • metadata            - optional metadata dict.

    Returns:
      A TaskSendParams where `message.parts` contains a single Part (TextPart or DataPart)
      constructed from `payload`, and all other fields set as passed.
    """
    # Build the single Part from payload
    if isinstance(payload, str):
        parts: List[Part] = [TextPart(type="text", text=payload, metadata=None)]
    else:
        parts = [DataPart(type="data", data=payload or {}, metadata=None)]

    # Construct the A2A Message
    msg = Message(role=role, parts=parts, metadata=None)

    return TaskSendParams(
        id=id,
        sessionId=session_id or id,
        message=msg,
        acceptedOutputModes=accepted_output_modes,
        pushNotification=push_notification,
        historyLength=history_length,
        metadata=metadata,
    )


def make_task(
    *,
    id: str,
    role: Literal["user", "agent"] = "agent",
    state: TaskState = TaskState.WORKING,
    payload: dict[str, Any] | str,
    session_id: Optional[str] = None,
) -> Task:
    task_data: List[Part] = []
    if isinstance(payload, str):
        task_data = [TextPart(text=payload)] if payload is not None else []
    else:
        task_data = [DataPart(data=payload)] if payload is not None else []
    return Task(
        id=id,
        sessionId=session_id or id,
        status=TaskStatus(
            state=state,
            message=Message(
                role=role,
                parts=task_data,
            ),
        ),
    )


def make_message(
    payload: dict[str, Any] | str | None,
    role: Literal["user", "agent"] = "agent",
) -> Optional[Message]:
    if payload is None:
        return None
    task_data: List[Part] = []
    if isinstance(payload, str):
        task_data = [TextPart(text=payload)] if payload is not None else []
    else:
        task_data = [DataPart(data=payload)] if payload is not None else []
    return Message(
        role=role,
        parts=task_data,
    )
