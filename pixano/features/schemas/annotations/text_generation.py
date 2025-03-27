# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import model_validator

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@dataclass
class Answer:
    """Holds the parts of an answer for multi-choices questions.

    Raises:
        ValueError: in case of parsing error at initialisation
    """

    content: str
    _choices: list[str]
    _explanation: str

    @classmethod
    def parse(cls, content: str) -> tuple[str, list[str], str]:
        """Utility function that parses a str content into the 3 fields of the Answer object.

        The input should be formated as follow "[[A;B;C]] this is a justification."

        Returns:
            content, the reformated content
            choices, the list of parsed answer elements
            explanation, the explanation sentence
        """
        choices = []
        explanation = ""
        try:
            re_choices_explanation = r"\[\[([a-zA-Z0-9]+(\;[a-zA-Z0-9]+)*)\]\]\s*(.*)"
            match_1 = re.match(re_choices_explanation, content)
            if match_1:
                explanation = str(match_1.groups()[-1])
                match_2 = re.findall(r"[a-zA-Z0-9]+", match_1.groups()[0])
                for m in match_2:
                    choices.append(m)
            content = Answer.format(choices, explanation)
        except Exception:
            raise ValueError(f"could not parse answer message : {content} => {choices}, {explanation}")
        return content, choices, explanation

    @classmethod
    def format(cls, choices, explanation):
        """Formats the message content for frontend.

        Returns:
            str: formated message content
        """
        return "[[{0}]] {1}".format(";".join(choices), explanation)

    def __init__(self, content: str):
        """Constructor of the Answer from a lazy formated message.

        Exemple of content : "[[A;B;C]] this is a justification."

        Args:
            content (str): lazy formated content of the message.
        """
        self.content, self._choices, self._explanation = Answer.parse(content)

    def __str__(self):
        """Formats the message content for frontend.

        Returns:
            str: formated message content
        """
        return Answer.format(self._choices, self._explanation)


@_register_schema_internal
class Message(Annotation):
    """Textual exchange in a question/answer conversation
    for image or text description and information extraction.

    Attributes:
        number: message number to associate different ANSWER messages to a QUESTION.
        content: actual text of the message.
        user: identify who is the author of the message (eg a human, a model, the ground truth, etc).
        choices: list of allowed answers, for 'Multiple Choice Question' when type=QUESTION and question_type!=OPEN.
        timestamp: creation date of the message.
        type: type of the message within "SYSTEM", "QUESTION" or "ANSWER".
            - SYSTEM: used for prefix messages stating the context. No associated answer expected
            - QUESTION: used to ask a question about a View. Expecting at least one answer (same message number)
            - ANSWER: used to reply to a question message by refering its message number
        question_type: type of question, specifying how to read and parse the content field.
            Authorized calued within "OPEN", "SINGLE_CHOICE", "SINGLE_CHOICE_EXPLANATION",
                                     "MULTI_CHOICE", "MULTI_CHOICE_EXPLANATION".
            - OPEN: used for any open question, where no specific format of answer is expected
            - SINGLE_CHOICE: used for a multi-choice-question where only one answer is authorized.
            - SINGLE_CHOICE_EXPLANATION: similar to SINGLE_CHOICE, but an explanation is expected
                    after the choosen answer. Cf Answer object
            - MULTI_CHOICE: used for a multi-choice-question where multi answers are authorized.
            - MULTI_CHOICE_EXPLANATION: similar to MULTI_CHOICE, but an explanation is expected
                    after the choosen answers. Cf Answer object
    """

    content: str
    number: int
    user: str
    type: str
    question_type: str = "OPEN"
    choices: list[str] = []
    timestamp: datetime = datetime(1, 1, 1, 0, 0, 0, 0)

    @model_validator(mode="before")
    def _check_data(data):
        if "type" not in data:
            raise ValueError("the message expect a type, either QUESTION or ANSWER.")
        data["type"] = data.get("type").upper()
        data["question_type"] = data.get("question_type", "OPEN").upper()
        data["choices"] = data.get("choices", [])
        if data["type"] == "QUESTION":
            if data["question_type"] == "OPEN" and len(data["choices"]) > 0:
                data["question_type"] = "MULTI_CHOICE"
            elif data["question_type"] != "OPEN" and len(data["choices"]) == 0:
                data["question_type"] = "OPEN"

        if data["type"] == "ANSWER":
            if data["question_type"] != "OPEN":
                answer = Answer(data["content"])
                if "_EXPLANATION" in data["question_type"] and answer._explanation == "":
                    raise ValueError("the question type expect an explanation in the answer.")
                if "SINGLE_" in data["question_type"] and len(answer._choices) > 1:
                    raise ValueError("the question type expect only one selected choice in the answer.")
                data["content"] = str(answer)
        return data

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.number < 0:
            raise ValueError("number should be a positive or null integer")
        elif self.type not in ["SYSTEM", "QUESTION", "ANSWER"]:
            raise ValueError("Message type should be 'SYSTEM', 'QUESTION', or 'ANSWER'.")
        if self.type != "QUESTION" and len(self.choices) > 0:
            raise ValueError(
                f"specifying MCQ anwsers is only allowed for Message of type 'QUESTION'. type={self.type}."
            )
        if self.type == "QUESTION" and self.question_type not in [
            "OPEN",
            "SINGLE_CHOICE",
            "SINGLE_CHOICE_EXPLANATION",
            "MULTI_CHOICE",
            "MULTI_CHOICE_EXPLANATION",
        ]:
            raise ValueError(
                "Question type should be 'OPEN',"
                " 'SINGLE_CHOICE', 'SINGLE_CHOICE_EXPLANATION',"
                " 'MULTI_CHOICE', or 'MULTI_CHOICE_EXPLANATION'."
            )
        if self.type == "QUESTION" and self.question_type != "OPEN" and not self.choices:
            raise ValueError(f"MCQ should have a list of available choices: {self}")
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
            choices=[],
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
    choices: list[str] = [],
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
        choices: list of allowed answers
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
        choices=choices,
        timestamp=timestamp,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )
