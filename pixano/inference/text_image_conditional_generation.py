# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

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

from pixano.datasets import Dataset
from pixano.features import Conversation, EntityRef, Message, SchemaGroup, Source, SourceRef, is_bbox


DEFAULT_ROLE_SYSTEM = "system"
DEFAULT_ROLE_USER = "user"
DEFAULT_ROLE_ASSISTANT = "assistant"
DEFAULT_TEMPERATURE = 0.9
DEFAULT_MAX_NEW_TOKENS = 100


def messages_to_prompt(
    dataset: Dataset,
    conversation: Conversation,
    messages: list[Message],
    media_dir: Path,
    role_system: str = DEFAULT_ROLE_SYSTEM,
    role_user: str = DEFAULT_ROLE_USER,
    role_assistant: str = DEFAULT_ROLE_ASSISTANT,
) -> list[dict[str, Any]]:
    """Convert a list of messages to a prompt.

    Args:
        dataset: The Pixano dtaset.
        conversation: The conversation entity of the messages.
        messages: List of messages.
        media_dir: The directory containing the images.
        role_system: The role to use for the system.
        role_user: The role to use for the user.
        role_assistant: The role to use for the assistant.

    Returns:
        List of dictionaries representing the prompt.
    """
    prompt = []
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

        ## add images to prompt
        tables_view = sorted(dataset.schema.groups[SchemaGroup.VIEW])
        for table_view in tables_view:
            images = dataset.get_data(table_view, item_ids=[conversation.item_ref.id])
            if len(images) > 0:
                image = images[0]  # there should be only one image per view, except for video (out of scope now)
                message_prompt["content"].append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image.url if is_url(image.url) else image.open(media_dir, "base64")},
                    }
                )

        ## add objects (bbox) to prompt
        tables_entities = sorted(dataset.schema.groups[SchemaGroup.ENTITY])
        tables_bbox = [k for k, v in dataset.schema.schemas.items() if is_bbox(v)]
        if len(tables_bbox) > 0:
            table_bbox = tables_bbox[0]  # assume there is only one bbox table
            for table_entity in tables_entities:
                entities = dataset.get_data(table_entity, item_ids=[conversation.item_ref.id])
                for entity in entities:
                    if not isinstance(entity, Conversation):
                        bboxes = dataset.get_data(
                            table_bbox, item_ids=[conversation.item_ref.id], where=f"entity_ref.id == '{entity.id}'"
                        )
                        if len(bboxes) == 0:
                            continue
                        bbox = bboxes[0]  # assume only one bbox per entity
                        bbox_text = f"a {'normalized ' if bbox.is_normalized else ''}bounding box {bbox.coords}"
                        if hasattr(entity, "name"):
                            bbox_text = bbox_text + f" with the name '{entity.name}'"
                        message_prompt["content"].append(
                            {
                                "type": "text",
                                "text": bbox_text,
                            }
                        )

        message_prompt["content"].append({"type": "text", "text": message.content})
        prompt.append(message_prompt)
    return prompt


async def text_image_conditional_generation(
    client: PixanoInferenceClient,
    source: Source,
    dataset: Dataset,
    media_dir: Path,
    messages: list[Message],
    conversation: Conversation,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    role_system: str = DEFAULT_ROLE_SYSTEM,
    role_user: str = DEFAULT_ROLE_USER,
    role_assistant: str = DEFAULT_ROLE_ASSISTANT,
    **client_kwargs: Any,
) -> Message:
    """Generate text from an image using the Pixano Inference API.

    Args:
        client: The Pixano-Inference client to use.
        source: The source refering to the model.
        dataset: The Pixano dataset.
        media_dir: The directory containing the input media files.
        messages: A list of Message objects representing the input messages.
        conversation: The conversation entity of the messages.
        max_new_tokens: The maximum number of tokens to generate.
        temperature: The temperature to use for sampling.
        role_system: The role of the system in the prompt.
        role_user: The role of the user in the prompt.
        role_assistant: The role of the assistant in the prompt.
        client_kwargs: Additional kwargs for the client to be passed.

    Returns:
        The response message and its source.
    """
    prompt = messages_to_prompt(
        dataset=dataset,
        conversation=conversation,
        messages=messages,
        media_dir=media_dir,
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
