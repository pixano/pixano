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
  type MessageType,
  type Reference,
} from "@pixano/core";

import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
import { getPixanoSource } from "../api/objectsApi";

export const createNewQuestion = (props: {
  number: number;
  content: string;
  choices: string[];
  question_type: QuestionTypeEnum;
  item_ref: Reference;
  view_ref: Reference;
  entity_ref: Reference;
}) => {
  const now = new Date().toISOString().replace(/Z$/, "+00:00");
  const pixanoSource = getPixanoSource(sourcesStore);

  const messageData: MessageType = {
    number: props.number,
    user: "user",
    timestamp: now,
    content: props.content,
    type: MessageTypeEnum.QUESTION,
    choices: props.choices,
    question_type: props.question_type,
  };

  return new Message({
    id: nanoid(22),
    table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
    created_at: now,
    updated_at: now,
    data: {
      item_ref: props.item_ref,
      view_ref: props.view_ref,
      entity_ref: props.entity_ref,
      source_ref: { name: pixanoSource.table_info.name, id: pixanoSource.id },
      ...messageData,
    },
  });
};
