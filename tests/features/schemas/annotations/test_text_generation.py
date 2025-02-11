# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import numpy as np
import pytest
from pydantic_core._pydantic_core import ValidationError

from pixano.features import Message, create_message, is_message
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


class TestMessage:
    def test_constructor(self):
        with pytest.raises(ValidationError, match="the message expect a type, either QUESTION or ANSWER."):
            Message()
        with pytest.raises(ValidationError):
            Message(number=-1, user="abc", type="SYSTEM", content="You are a kind image annotator")
        with pytest.raises(ValidationError):
            Message(number=0, user="abc", type="TBD", content="You are a kind image annotator")

        current_date = datetime.now()
        msg1 = Message(
            number=0,
            user="abc",
            type="SYSTEM",
            content="You are a kind image-text annotator",
            timestamp=current_date,
        )
        assert msg1.timestamp == current_date

        msg2 = Message(number=0, user="abc", type="QUESTION", content="Write a 500-word summary of this document.")
        assert msg2.user == "abc"
        assert msg2.type == "QUESTION"
        assert msg2.content == "Write a 500-word summary of this document."
        assert msg2.choices == []

        msg3 = Message(
            number=1,
            user="abc",
            type="QUESTION",
            content="What is your favourite color?",
            choices=["R : red", "B : blue"],
        )
        assert msg3.user == "abc"
        assert msg3.type == "QUESTION"
        assert msg3.content == "What is your favourite color?"
        assert msg3.choices == ["R : red", "B : blue"]

        msg4 = Message(number=2, user="def", type="ANSWER", content="B")
        assert msg4.user == "def"
        assert msg4.type == "ANSWER"
        assert msg4.content == "B"
        assert msg4.choices == []

        with pytest.raises(ValidationError):
            msg5 = Message(number=2, user="ghi", type="ANSWER", content="B", choices=["R : red", "B : blue"])
            del msg5

        msg6 = Message(
            number=3,
            user="jkl",
            type="QUESTION",
            question_type="SINGLE_CHOICE",
            content="What is the airspeed velocity of an unladen swallow?",
            choices=["European swallow", "African swallow"],
        )
        assert msg6.user == "jkl"
        assert msg6.type == "QUESTION"
        assert msg6.question_type == "SINGLE_CHOICE"
        assert msg6.content == "What is the airspeed velocity of an unladen swallow?"
        assert msg6.choices == ["European swallow", "African swallow"]

        msg7 = Message(
            number=3,
            user="jkl",
            type="ANSWER",
            question_type="SINGLE_CHOICE_EXPLANATION",
            content="[[1]]   The african swallow is faster",
        )
        assert msg7.user == "jkl"
        assert msg7.type == "ANSWER"
        assert msg7.question_type == "SINGLE_CHOICE_EXPLANATION"
        assert msg7.content == "[[1]] The african swallow is faster"

    def test_none(self):
        none_msg = Message.none()
        assert none_msg.id == ""
        assert none_msg.item_ref == ItemRef.none()
        assert none_msg.view_ref == ViewRef.none()
        assert none_msg.entity_ref == EntityRef.none()
        assert none_msg.source_ref == SourceRef.none()
        assert none_msg.user == ""
        assert none_msg.content == ""
        assert none_msg.choices == []
        assert none_msg.type == "QUESTION"


def test_is_message():
    make_tests_is_sublass_strict(is_message, Message)


def test_create_message():
    # Test 1: default references
    msg = create_message(number=0, user="abc", type="QUESTION", content="Write a 500-word summary of this document.")
    assert isinstance(msg, Message)
    assert msg.user == "abc"
    assert msg.type == "QUESTION"
    assert msg.content == "Write a 500-word summary of this document."
    assert msg.id == ""
    assert msg.item_ref == ItemRef.none()
    assert msg.view_ref == ViewRef.none()
    assert msg.entity_ref == EntityRef.none()
    assert msg.source_ref == SourceRef.none()

    # Test 2: with references
    msg = create_message(
        number=0,
        user="abc",
        type="QUESTION",
        content="Write a 500-word summary of this document.",
        id="msg_1",
        item_ref=ItemRef(id="item_1"),
        view_ref=ViewRef(id="view_1", name="text"),
        entity_ref=EntityRef(id="entity_1", name="entity"),
    )
    assert isinstance(msg, Message)
    assert msg.id == "msg_1"
    assert msg.item_ref == ItemRef(id="item_1")
    assert msg.view_ref == ViewRef(id="view_1", name="text")
    assert msg.entity_ref == EntityRef(id="entity_1", name="entity")
