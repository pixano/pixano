# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pydantic_core import ValidationError

from pixano.features import Conversation, Message, create_conversation, is_conversation
from tests.features.utils import make_tests_is_sublass_strict


class TestConversation:
    def test_constructor_sorts_messages(self):
        conversation = Conversation(
            conversation_id="conv_0",
            messages=[
                Message(conversation_id="conv_0", number=1, user="model", type="ANSWER", content="blue"),
                Message(
                    conversation_id="conv_0",
                    number=0,
                    user="human",
                    type="QUESTION",
                    content="color?",
                    question_type="OPEN",
                ),
            ],
        )

        assert [message.number for message in conversation.messages] == [0, 1]

    def test_constructor_rejects_mixed_conversation_ids(self):
        with pytest.raises(ValidationError, match="All messages must belong to conversation 'conv_0'"):
            Conversation(
                conversation_id="conv_0",
                messages=[
                    Message(
                        conversation_id="conv_1",
                        number=0,
                        user="human",
                        type="QUESTION",
                        content="color?",
                        question_type="OPEN",
                    ),
                ],
            )


def test_is_conversation():
    make_tests_is_sublass_strict(is_conversation, Conversation)


def test_create_conversation():
    message = Message(
        conversation_id="conv_0",
        number=0,
        user="human",
        type="QUESTION",
        content="color?",
        question_type="OPEN",
    )
    conversation = create_conversation("conv_0", [message])
    assert conversation.conversation_id == "conv_0"
    assert conversation.messages == [message]
