/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Message, MessageTypeEnum, type MessageType } from "@pixano/core";
import { nanoid } from "nanoid";
import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
import { getPixanoSource } from "../api/objectsApi";

export const createNewAnswer = ({
  question,
  content,
  answers,
  explanations,
}: {
  question: Message;
  content: string;
  answers?: string[];
  explanations?: string[];
}) => {
  const now = new Date().toISOString();
  const pixanoSource = getPixanoSource(sourcesStore);

  const messageData: MessageType = {
    number: question.data.number,
    user: "user",
    content,
    timestamp: now,
    type: MessageTypeEnum.ANSWER,
    answers: answers ?? [],
    explanations: explanations ?? [],
  };

  return new Message({
    id: nanoid(10),
    table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
    created_at: now,
    updated_at: now,
    data: {
      ...question.data,
      ...messageData,
      source_ref: { name: pixanoSource.table_info.name, id: pixanoSource.id },
    },
  });
};
