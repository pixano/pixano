# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime
from typing import Literal

from pydantic import model_validator

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class Message(Annotation):
    """Textual exchange in a question/answer conversation
    for image or text description and information extraction.

    Attributes:
        number: message number to associate different ANSWER messages to a QUESTION.
        user: identify who is the author of the message (eg a human, a model, the ground truth, etc).
        content: actual text of the message.
        timestamp: creation date of the message.
        type: type of the message within "SYSTEM", "QUESTION" or"ANSWER".
            - SYSTEM: used for prefix messages stating the context. No associated answer expected
            - QUESTION: used to ask a question about a View. Expecting at least one answer (same message number)
            - ANSWER: used to reply to a question message by refering its message number
    """

    number: int
    user: str
    type: str
    content: str
    timestamp: datetime = datetime(1, 1, 1, 0, 0, 0, 0)

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.number < 0:
            raise ValueError("number should be a positive or null integer")
        elif self.type not in ["SYSTEM", "QUESTION", "ANSWER"]:
            raise ValueError("Message type be 'SYSTEM', 'QUESTION', 'ANSWER'.")
        return self

    @classmethod
    def none(cls) -> "Message":
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            "None" Message.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            source_ref=SourceRef.none(),
            number=0,
            user="",
            type="QUESTION",
            content="",
            timestamp=datetime(1, 1, 1, 0, 0, 0, 0),
        )


def is_message(cls: type, strict: bool = False) -> bool:
    """Check if a class is a Message or subclass of Message."""
    return issubclass_strict(cls, Message, strict)


def create_message(
    number: int,
    user: str,
    type: Literal["SYSTEM", "QUESTION", "ANSWER"],
    content: str,
    timestamp: datetime = datetime(1, 1, 1, 0, 0, 0, 0),
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> Message:
    """Create a Message instance.

    Args:
        number: message number to associate diffrent ANSWER messages to a QUESTION
        user: identify who is the author of the message (eg a human, a model, the ground truth, etc)
        type: type of the message within "SYSTEM", "QUESTION" or"ANSWER"
        content: actual text of the message
        timestamp: creation date of the message
        id: object id
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `Message` instance.
    """
    return Message(
        number=number,
        user=user,
        type=type,
        content=content,
        timestamp=timestamp,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )
