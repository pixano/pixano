from pydantic import model_validator

from pixano.utils import issubclass_strict

from .entity_group_annotation import EntityGroupAnnotation


class Message(EntityGroupAnnotation):
    """One conversational turn grouped by ``conversation_id``."""

    conversation_id: str
    number: int
    user: str
    type: str
    content: str
    choices: list[str] = []

    @model_validator(mode="before")
    def _normalize(cls, data):
        if "type" not in data:
            raise ValueError("message type is required")
        data["type"] = str(data.get("type")).upper()
        data["choices"] = list(data.get("choices", []))
        data["entity_ids"] = list(data.get("entity_ids", []))
        return data

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.number < 0:
            raise ValueError("number must be greater than or equal to 0")
        if self.type not in {"SYSTEM", "QUESTION", "ANSWER"}:
            raise ValueError("type must be one of SYSTEM, QUESTION, ANSWER")
        if self.type != "QUESTION" and self.choices:
            raise ValueError("choices are only valid for QUESTION messages")
        return self

    @classmethod
    def none(cls) -> "Message":
        return cls(
            id="",
            conversation_id="",
            number=0,
            user="",
            type="QUESTION",
            content="",
            choices=[],
            entity_ids=[],
        )


def is_message(cls: type, strict: bool = False) -> bool:
    """Check if a class is a Message or subclass of Message."""

    return issubclass_strict(cls, Message, strict)


def create_message(
    conversation_id: str,
    number: int,
    user: str,
    type: str,
    content: str,
    choices: list[str] = [],
    entity_ids: list[str] = [],
    id: str = "",
    record_id: str = "",
    view_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
) -> Message:
    """Create a Message instance.

    Args:
        conversation_id: Conversation ID.
        number: Message number in conversation.
        user: User who sent the message.
        type: Message type (SYSTEM, QUESTION, ANSWER).
        content: Message content.
        choices: Choices for QUESTION messages.
        entity_ids: IDs of referenced entities.
        id: Message ID.
        record_id: Record ID.
        view_id: View ID.
        source_type: Source type.
        source_name: Source name.
        source_metadata: Source metadata (JSON string).

    Returns:
        The created `Message` instance.
    """
    return Message(
        conversation_id=conversation_id,
        number=number,
        user=user,
        type=type,
        content=content,
        choices=choices,
        entity_ids=entity_ids,
        id=id,
        record_id=record_id,
        view_id=view_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
    )
