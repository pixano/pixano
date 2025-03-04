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
  type Reference,
} from "@pixano/core";

// Importing apps' store from datasetItemWorkspace is bad
// getPixanoSource should be in apps or both should be in datasetItemWorkspace
import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
import { getPixanoSource } from "../api/objectsApi";

// We have to define once more all the types of message here because there are passthroughs on
// every zod schema...

/* eslint-disable @typescript-eslint/no-explicit-any */
type InferenceMetadata = Record<string, any>;

interface CreateMessageBaseProps {
  number: number;
  content: string;
  choices: string[];
  item_ref: Reference;
  view_ref: Reference;
  entity_ref: Reference;
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

export const createNewMessage = (props: CreateMessageProps) => {
  const now = new Date().toISOString().replace(/Z$/, "+00:00");
  const pixanoSource = getPixanoSource(sourcesStore);

  return new Message({
    id: nanoid(22),
    table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
    created_at: now,
    updated_at: now,
    data: {
      ...props,
      timestamp: now,
      source_ref: { name: pixanoSource.table_info.name, id: pixanoSource.id },
    },
  });
};
