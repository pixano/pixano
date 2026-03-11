"""Read-only conversation aggregate endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from pixano.datasets import Dataset

from pixano.api.models import ConversationResponse, MessageResponse, PaginatedResponse, serialize_row
from pixano.api.resources import MESSAGE_RESOURCE
from pixano.api.routers._deps import FilterParams, PaginationParams, get_dataset_dep
from pixano.api.service import BaseService


router = APIRouter(prefix="/datasets/{dataset_id}/conversations", tags=["Conversations"])


def _conversation_response(conversation) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        messages=[MessageResponse.model_validate(serialize_row(message)) for message in conversation.messages],
    )


@router.get("", response_model=PaginatedResponse[ConversationResponse])
def list_conversations(
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
) -> PaginatedResponse[ConversationResponse]:
    """List conversation aggregates reconstructed from message rows."""

    table_name = BaseService(dataset, MESSAGE_RESOURCE).resolve_table()
    conversations, total = dataset.get_conversations(
        table_name=table_name,
        record_id=filters.record_id,
        entity_id=filters.entity_id,
        view_id=filters.view_name,
        source_type=filters.source_type,
        where=filters.where,
        limit=pagination.limit,
        skip=pagination.offset,
    )
    return PaginatedResponse(
        items=[_conversation_response(conversation) for conversation in conversations],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
) -> ConversationResponse:
    """Get one conversation aggregate by conversation id."""

    table_name = BaseService(dataset, MESSAGE_RESOURCE).resolve_table()
    conversation = dataset.get_conversation(table_name=table_name, conversation_id=conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    return _conversation_response(conversation)
