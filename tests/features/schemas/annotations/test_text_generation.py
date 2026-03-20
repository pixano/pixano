# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pydantic_core import ValidationError

from pixano.features import Message, create_message, is_message
from tests.features.utils import make_tests_is_sublass_strict


class TestMessage:
    def test_constructor(self):
        with pytest.raises(ValidationError, match="message type is required"):
            Message()
        with pytest.raises(ValidationError, match="number must be greater than or equal to 0"):
            Message(
                conversation_id="conv_0",
                number=-1,
                user="abc",
                type="QUESTION",
                content="hello",
                question_type="OPEN",
            )
        with pytest.raises(ValidationError, match="type must be one of SYSTEM, QUESTION, ANSWER"):
            Message(conversation_id="conv_0", number=0, user="abc", type="TBD", content="hello")
        with pytest.raises(ValidationError, match="choices are only valid for QUESTION messages"):
            Message(conversation_id="conv_0", number=1, user="abc", type="ANSWER", content="B", choices=["A", "B"])
        with pytest.raises(ValidationError, match="question_type is required for QUESTION messages"):
            Message(conversation_id="conv_0", number=0, user="abc", type="QUESTION", content="hello")
        with pytest.raises(ValidationError, match="question_type is only valid for QUESTION messages"):
            Message(
                conversation_id="conv_0",
                number=1,
                user="model",
                type="ANSWER",
                content="B",
                question_type="OPEN",
            )

        msg = Message(
            conversation_id="conv_0",
            number=0,
            user="abc",
            type="question",
            content="What is your favourite color?",
            choices=["R : red", "B : blue"],
            question_type="SINGLE_CHOICE",
            entity_ids=["entity_0"],
        )
        assert msg.type == "QUESTION"
        assert msg.choices == ["R : red", "B : blue"]
        assert msg.question_type == "SINGLE_CHOICE"
        assert msg.entity_ids == ["entity_0"]

        answer = Message(
            conversation_id="conv_0",
            number=1,
            user="model",
            type="ANSWER",
            content="B",
        )
        assert answer.type == "ANSWER"
        assert answer.choices == []
        assert answer.entity_ids == []

    def test_none(self):
        none_msg = Message.none()
        assert none_msg.id == ""
        assert none_msg.record_id == ""
        assert none_msg.view_id == ""
        assert none_msg.entity_ids == []
        assert none_msg.source_type == ""
        assert none_msg.source_name == ""
        assert none_msg.conversation_id == ""
        assert none_msg.user == ""
        assert none_msg.content == ""
        assert none_msg.choices == []
        assert none_msg.question_type == "OPEN"
        assert none_msg.type == "QUESTION"


def test_is_message():
    make_tests_is_sublass_strict(is_message, Message)


def test_create_message():
    msg = create_message(
        conversation_id="conv_0",
        number=0,
        user="abc",
        type="QUESTION",
        content="Write a summary.",
        choices=["short", "long"],
        question_type="SINGLE_CHOICE",
        entity_ids=["entity_1"],
        id="msg_1",
        record_id="item_1",
        view_id="text",
        source_type="model",
        source_name="source_1",
    )
    assert isinstance(msg, Message)
    assert msg.id == "msg_1"
    assert msg.record_id == "item_1"
    assert msg.view_id == "text"
    assert msg.entity_ids == ["entity_1"]
    assert msg.source_type == "model"
    assert msg.source_name == "source_1"
    assert msg.conversation_id == "conv_0"
    assert msg.choices == ["short", "long"]
    assert msg.question_type == "SINGLE_CHOICE"
