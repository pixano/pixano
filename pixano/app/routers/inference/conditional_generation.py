# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from pixano.app.models import AnnotationModel
from pixano.app.models.entities import EntityModel
from pixano.app.routers.inference.utils import get_client_from_settings
from pixano.app.routers.utils import get_dataset
from pixano.app.settings import Settings, get_settings
from pixano.features import Conversation, Message
from pixano.features.schemas.annotations.text_generation import is_message
from pixano.features.schemas.entities.conversation import is_conversation
from pixano.inference.text_image_conditional_generation import (
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_ROLE_ASSISTANT,
    DEFAULT_ROLE_SYSTEM,
    DEFAULT_ROLE_USER,
    DEFAULT_TEMPERATURE,
    text_image_conditional_generation,
)

from .utils import get_model_source


router = APIRouter(prefix="/tasks/conditional_generation", tags=["Task", "Conditional Generation"])


@router.post(
    "/text-image",
    response_model=AnnotationModel,
)
async def call_text_image_conditional_generation(
    dataset_id: Annotated[str, Body(embed=True)],
    conversation: Annotated[EntityModel, Body(embed=True)],
    messages: Annotated[list[AnnotationModel], Body(embed=True)],
    model: Annotated[str, Body(embed=True)],
    settings: Annotated[Settings, Depends(get_settings)],
    max_new_tokens: Annotated[int, Body(embed=True)] = DEFAULT_MAX_NEW_TOKENS,
    temperature: Annotated[float, Body(embed=True)] = DEFAULT_TEMPERATURE,
    role_system: Annotated[str, Body(embed=True)] = DEFAULT_ROLE_SYSTEM,
    role_user: Annotated[str, Body(embed=True)] = DEFAULT_ROLE_USER,
    role_assistant: Annotated[str, Body(embed=True)] = DEFAULT_ROLE_ASSISTANT,
) -> AnnotationModel:
    """Call a text image conditional generation model for a conversation.

    Args:
        dataset_id: The ID of the dataset to use.
        conversation: The conversation to use.
        messages: The messages to use.
        model: The name of the model to use.
        settings: App settings.
        max_new_tokens: The maximum number of tokens to generate.
        temperature: The temperature to use.
        role_system: The role of the system.
        role_user: The role of the user.
        role_assistant: The role of the assistant.

    Returns: The generated message model.
    """
    dataset = get_dataset(dataset_id=dataset_id, dir=settings.library_dir, media_dir=settings.media_dir)
    client = get_client_from_settings(settings=settings)

    if not is_conversation(dataset.schema.schemas[conversation.table_info.name]):
        raise HTTPException(status_code=400, detail="Conversation must be a conversation.")

    conversation_row: Conversation = conversation.to_row(dataset)

    messages_in_one_table = len({m.table_info.name for m in messages}) == 1
    if not messages_in_one_table:
        raise HTTPException(status_code=400, detail="Only one table for messages is allowed.")
    elif not is_message(dataset.schema.schemas[messages[0].table_info.name]):
        raise HTTPException(status_code=400, detail="Messages must be a message.")

    messages_rows: list[Message] = []
    for m in messages:
        m_row: Message = m.to_row(dataset)
        messages_rows.append(m_row)

    source = get_model_source(dataset=dataset, model=model)

    try:
        infered_message = await text_image_conditional_generation(
            client=client,
            source=source,
            dataset=dataset,
            media_dir=settings.media_dir,
            messages=messages_rows,
            conversation=conversation_row,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            role_system=role_system,
            role_user=role_user,
            role_assistant=role_assistant,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    message_model = AnnotationModel.from_row(row=infered_message, table_info=messages[0].table_info)

    return message_model
