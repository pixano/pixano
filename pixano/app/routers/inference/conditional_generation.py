# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

import shortuuid
from fastapi import APIRouter, Depends, HTTPException

from pixano.app.models import AnnotationModel
from pixano.app.models.entities import EntityModel
from pixano.app.routers.inference.utils import get_client_from_settings
from pixano.app.routers.utils import get_dataset
from pixano.app.settings import Settings, get_settings
from pixano.features import Source
from pixano.inference.text_image_conditional_generation import (
    DEFAULT_IMAGE_REGEX,
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_ROLE_ASSISTANT,
    DEFAULT_ROLE_SYSTEM,
    DEFAULT_ROLE_USER,
    DEFAULT_TEMPERATURE,
    text_image_conditional_generation,
)


router = APIRouter(prefix="/task/conditional_generation", tags=["Task", "Conditional Generation"])


@router.post(
    "/image-text",
    response_model=AnnotationModel,
)
async def call_text_image_conditional_generation(
    dataset_id: str,
    conversation: EntityModel,
    messages: list[AnnotationModel],
    model: str,
    settings: Annotated[Settings, Depends(get_settings)],
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    image_regex: str = DEFAULT_IMAGE_REGEX,
    role_system: str = DEFAULT_ROLE_SYSTEM,
    role_user: str = DEFAULT_ROLE_USER,
    role_assistant: str = DEFAULT_ROLE_ASSISTANT,
) -> AnnotationModel:
    """Call a text image conditional generation model for a conversation.

    Args:
        dataset_id: The ID of the dataset to use.
        conversation: The conversation to use.
        messages: The messages to use.
        model: The name of the model to use.
        source: The source to use.
        settings: App settings.
        max_new_tokens: The maximum number of tokens to generate.
        temperature: The temperature to use.
        image_regex: The regular expression to use to extract images from the text.
        role_system: The role of the system.
        role_user: The role of the user.
        role_assistant: The role of the assistant.

    Returns: The generated message model.
    """
    dataset = get_dataset(dataset_id=dataset_id, dir=settings.library_dir, media_dir=settings.media_dir)
    client = get_client_from_settings(settings=settings)

    conversation_row = conversation.to_row(schema_type=dataset.schema.schemas[conversation.table_info.name])

    messages_in_one_table = len({m.table_info.name for m in messages}) == 1
    if not messages_in_one_table:
        raise HTTPException(status_code=400, detail="Only one table for messages is allowed.")

    messages_rows = [m.to_row(schema_type=dataset.schema.schemas[messages[0].table_info.name]) for m in messages]

    sources: list[Source] = dataset.get_data(table_name="source", limit=2, where=f"name='{model}' AND kind='model'")
    if len(sources) > 1:
        raise HTTPException(status_code=400, detail="Only one source for model is allowed.")
    elif len(sources) == 0:
        source = Source(id=shortuuid.uuid(), name=model, kind="model")
        dataset.add_data("source", data=[source])
    else:
        source = sources[0]

    try:
        infered_message = text_image_conditional_generation(
            client=client,
            source=source,
            media_dir=settings.media_dir,
            messages=messages_rows,
            conversation=conversation_row,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            image_regex=image_regex,
            role_system=role_system,
            role_user=role_user,
            role_assistant=role_assistant,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    message_model = AnnotationModel.from_row(row=infered_message, table_info=messages[0].table_info)

    return message_model
