# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import re
from pathlib import Path
from typing import Any

import shortuuid
from fastapi.encoders import jsonable_encoder
from pixano_inference.client import PixanoInferenceClient
from pixano_inference.pydantic.tasks import (
    TextImageConditionalGenerationRequest,
    TextImageConditionalGenerationResponse,
)
from pixano_inference.utils import is_url

from pixano.features import Conversation, EntityRef, Image, Message, Source, SourceRef


DEFAULT_IMAGE_REGEX = r"<image(\s\d+)?>"
DEFAULT_ROLE_SYSTEM = "system"
DEFAULT_ROLE_USER = "user"
DEFAULT_ROLE_ASSISTANT = "assistant"
DEFAULT_TEMPERATURE = 0.9
DEFAULT_MAX_NEW_TOKENS = 100


def messages_to_prompt(
    messages: list[Message],
    media_dir: Path,
    image_regex: str = DEFAULT_IMAGE_REGEX,
    role_system: str = DEFAULT_ROLE_SYSTEM,
    role_user: str = DEFAULT_ROLE_USER,
    role_assistant: str = DEFAULT_ROLE_ASSISTANT,
) -> list[dict[str, Any]]:
    """Convert a list of messages to a prompt.

    Args:
        messages: List of messages.
        media_dir: The directory containing the images.
        image_regex: The tag used to represent an image in the messages.
        role_system: The role to use for the system.
        role_user: The role to use for the user.
        role_assistant: The role to use for the assistant.

    Returns:
        List of dictionaries representing the prompt.
    """
    prompt = []
    image_regex = rf"{image_regex}"
    used_images = 0
    for message in messages:
        message_prompt: dict[str, Any] = {"content": []}
        match message.type:
            case "SYSTEM":
                message_prompt["role"] = role_system
            case "QUESTION":
                message_prompt["role"] = role_user
            case "ANSWER":
                message_prompt["role"] = role_assistant
            case _:
                raise ValueError(f"Unknown message type {message.type}")
        find_all = re.findall(image_regex, message.content)
        num_images = len(find_all)
        if num_images > 0:
            image: Image = message.view
        for i in range(num_images):
            message_prompt["content"].append(
                {
                    "type": "image_url",
                    "image_url": {"url": image.url if is_url(image.url) else image.open(media_dir, "base64")},
                }
            )
        used_images += num_images
        message_content = message.content if num_images == 0 else re.sub(image_regex, "", message.content)
        message_prompt["content"].append({"type": "text", "text": message_content})
        prompt.append(message_prompt)
    return prompt


async def text_image_conditional_generation(
    client: PixanoInferenceClient,
    source: Source,
    media_dir: Path,
    messages: list[Message],
    conversation: Conversation,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    image_regex: str = DEFAULT_IMAGE_REGEX,
    role_system: str = DEFAULT_ROLE_SYSTEM,
    role_user: str = DEFAULT_ROLE_USER,
    role_assistant: str = DEFAULT_ROLE_ASSISTANT,
    **client_kwargs: Any,
) -> Message:
    """Generate text from an image using the Pixano Inference API.

    Args:
        client: The Pixano-Inference client to use.
        source: The source refering to the model.
        media_dir: The directory containing the input media files.
        messages: A list of Message objects representing the input messages.
        conversation: The conversation entity of the messages.
        max_new_tokens: The maximum number of tokens to generate.
        temperature: The temperature to use for sampling.
        image_regex: The tag used to represent an image in the messages.
        role_system: The role of the system in the prompt.
        role_user: The role of the user in the prompt.
        role_assistant: The role of the assistant in the prompt.
        client_kwargs: Additional kwargs for the client to be passed.

    Returns:
        The response message and its source.
    """
    prompt = messages_to_prompt(
        messages=messages,
        media_dir=media_dir,
        image_regex=image_regex,
        role_system=role_system,
        role_user=role_user,
        role_assistant=role_assistant,
    )
    last_message = messages[-1]
    match last_message.type:
        case "SYSTEM":
            response_type = "QUESTION"
            number = last_message.number + 1
        case "ANSWER":
            response_type = "QUESTION"
            number = last_message.number + 1
        case "QUESTION":
            response_type = "ANSWER"
            number = last_message.number
        case _:
            raise ValueError(f"Invalid last message type {last_message.type}")
    request = TextImageConditionalGenerationRequest(
        model=source.name,
        prompt=prompt,
        images=None,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
    )
    response: TextImageConditionalGenerationResponse = await client.text_image_conditional_generation(
        request, **client_kwargs
    )

    inference_metadata = jsonable_encoder(
        {
            "generation_config": response.data.generation_config,
            "usage": response.data.usage,
            "timestamp": response.timestamp,
            "processing_time": response.processing_time,
        }
    )

    message = Message(
        id=shortuuid.uuid(),
        item_ref=last_message.item_ref,
        view_ref=last_message.view_ref,
        entity_ref=EntityRef(id=conversation.id, name=conversation.table_name),
        source_ref=SourceRef(id=source.id),
        type=response_type,
        content=response.data.generated_text,
        number=number,
        user=source.name,
        timestamp=response.timestamp,
        inference_metadata=inference_metadata,
    )

    return message
