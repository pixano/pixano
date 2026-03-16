/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { BaseSchema, Message, MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";
import { nowTimestamp } from "$lib/utils/coreUtils";
import { PIXANO_SOURCE } from "$lib/utils/entityLookupUtils";

/* eslint-disable @typescript-eslint/no-explicit-any */
type InferenceMetadata = Record<string, any>;

interface CreateMessageBaseProps {
  number: number;
  content: string;
  choices: string[];
  record_id: string;
  view_id: string;
  entity_ids: string[];
  conversation_id: string;
  source_type?: string;
  source_name?: string;
  source_metadata?: string;
  item_id?: string;
  view_name?: string;
  entity_id?: string;
}

interface CreateQuestionProps extends CreateMessageBaseProps {
  question_type: QuestionTypeEnum;
  type: MessageTypeEnum.QUESTION;
  user: "user";
  inference_metadata: InferenceMetadata;
}

interface CreateSystemMessageProps extends CreateMessageBaseProps {
  type: MessageTypeEnum.SYSTEM;
  user: "system";
  inference_metadata: InferenceMetadata;
}

interface CreateAnswerProps extends CreateMessageBaseProps {
  type: MessageTypeEnum.ANSWER;
  user: "user";
  inference_metadata: InferenceMetadata;
}

type CreateMessageProps = CreateSystemMessageProps | CreateQuestionProps | CreateAnswerProps;

export interface MessageTransportPayload {
  id: string;
  record_id: string;
  entity_ids: string[];
  source_type: string;
  source_name: string;
  source_metadata: string;
  view_id: string;
  conversation_id: string;
  number: number;
  user: string;
  type: string;
  content: string;
  choices: string[];
  question_type?: QuestionTypeEnum;
}

function getMessageEntityIds(message: Message): string[] {
  if (Array.isArray(message.data.entity_ids)) {
    return message.data.entity_ids as string[];
  }
  if (typeof message.data.entity_id === "string" && message.data.entity_id !== "") {
    return [message.data.entity_id];
  }
  return [];
}

function stringifySourceMetadata(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value ?? {});
}

export const createMessage = (props: CreateMessageProps): Message => {
  const now = nowTimestamp();
  const sourceType = props.source_type ?? PIXANO_SOURCE.type;
  const sourceName = props.source_name ?? PIXANO_SOURCE.name;
  const sourceMetadata = props.source_metadata ?? PIXANO_SOURCE.metadata;

  return new Message({
    id: nanoid(22),
    table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
    created_at: now,
    updated_at: now,
    data: {
      ...props,
      item_id: props.item_id ?? props.record_id,
      record_id: props.record_id,
      view_id: props.view_id,
      view_name: props.view_name ?? "",
      entity_id: props.entity_id ?? props.entity_ids[0] ?? "",
      timestamp: now,
      source_type: sourceType,
      source_name: sourceName,
      source_metadata: sourceMetadata,
      inference_metadata: props.inference_metadata,
    },
  });
};

export const updateMessage = ({
  prevMessage,
  content,
}: {
  prevMessage: Message;
  content: string;
}): Message => {
  const { ui, ...rest } = prevMessage;
  void ui;

  if ("_constructor-name_" in rest) {
    delete (rest as Record<string, unknown>)["_constructor-name_"];
  }

  return new Message({
    ...rest,
    data: {
      ...rest.data,
      content,
    },
  });
};

export function toMessageTransportPayload(message: Message): MessageTransportPayload {
  const entityIds = getMessageEntityIds(message);
  const payload: MessageTransportPayload = {
    id: message.id,
    record_id: (message.data.record_id as string) ?? message.data.item_id ?? "",
    entity_ids: entityIds,
    source_type: (message.data.source_type as string) ?? "other",
    source_name: (message.data.source_name as string) ?? "",
    source_metadata: stringifySourceMetadata(message.data.source_metadata),
    view_id: (message.data.view_id as string) ?? "",
    conversation_id: (message.data.conversation_id as string) ?? "",
    number: (message.data.number as number) ?? 0,
    user: (message.data.user as string) ?? "",
    type: (message.data.type as string) ?? MessageTypeEnum.QUESTION,
    content: (message.data.content as string) ?? "",
    choices:
      message.data.type === MessageTypeEnum.QUESTION
        ? ((message.data.choices as string[]) ?? [])
        : [],
  };

  if (message.data.type === MessageTypeEnum.QUESTION) {
    payload.question_type = message.data.question_type as QuestionTypeEnum;
  }

  return payload;
}
