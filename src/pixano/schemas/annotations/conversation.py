from pydantic import BaseModel, model_validator

from pixano.utils import issubclass_strict

from .message import Message


class Conversation(BaseModel):
    """Derived conversation aggregate reconstructed from grouped messages."""

    conversation_id: str
    messages: list[Message]

    @model_validator(mode="after")
    def _validate_messages(self) -> "Conversation":
        if not self.conversation_id:
            raise ValueError("conversation_id must not be empty")
        if not self.messages:
            raise ValueError("messages must not be empty")
        self.messages = sorted(self.messages, key=lambda message: message.number)
        invalid_messages = [message.id for message in self.messages if message.conversation_id != self.conversation_id]
        if invalid_messages:
            raise ValueError(
                f"All messages must belong to conversation '{self.conversation_id}'. Invalid message ids: {invalid_messages}"
            )
        return self

    @classmethod
    def from_messages(cls, messages: list[Message]) -> "Conversation":
        """Build a conversation aggregate from grouped messages."""

        if not messages:
            raise ValueError("messages must not be empty")
        return cls(conversation_id=messages[0].conversation_id, messages=messages)


def is_conversation(cls: type, strict: bool = False) -> bool:
    """Check if a class is a Conversation or subclass of Conversation."""

    return issubclass_strict(cls, Conversation, strict)


def create_conversation(conversation_id: str, messages: list[Message]) -> Conversation:
    """Create a Conversation aggregate."""

    return Conversation(conversation_id=conversation_id, messages=messages)
