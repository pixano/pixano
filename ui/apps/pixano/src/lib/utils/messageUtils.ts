/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import {
  BaseSchema,
  Message,
  MessageTypeEnum,
  QuestionTypeEnum,
} from "$lib/types/dataset";

import { sourcesStore } from "$lib/stores/appStores.svelte";
import { nowTimestamp } from "$lib/utils/coreUtils";
import { getPixanoSourceId } from "$lib/utils/entityLookupUtils";

/* eslint-disable @typescript-eslint/no-explicit-any */
type InferenceMetadata = Record<string, any>;

interface CreateMessageBaseProps {
  number: number;
  content: string;
  choices: string[];
  item_id: string;
  view_name: string;
  frame_id: string;
  entity_id: string;
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

export const createMessage = (props: CreateMessageProps): Message => {
  const now = nowTimestamp();
  const sourceId = getPixanoSourceId(sourcesStore);

  return new Message({
    id: nanoid(22),
    table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
    created_at: now,
    updated_at: now,
    data: {
      ...props,
      timestamp: now,
      source_id: sourceId,
      frame_index: -1,
      tracklet_id: "",
      entity_dynamic_state_id: "",
      inference_metadata: {},
    },
  });
};

export const updateAnswerMessage = ({
  prevAnswer,
  content,
}: {
  prevAnswer: Message;
  content: string;
}): Message => {
  const { ui, ...rest } = prevAnswer;
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
