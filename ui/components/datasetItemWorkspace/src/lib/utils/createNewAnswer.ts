/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { BaseSchema, Message, MessageTypeEnum, type MessageType } from "@pixano/core";

import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
import { getPixanoSource } from "../api/objectsApi";

export const createNewAnswer = ({ question, content }: { question: Message; content: string }) => {
  const now = new Date().toISOString().replace(/Z$/, "+00:00");
  const pixanoSource = getPixanoSource(sourcesStore);

  const messageData: MessageType = {
    number: question.data.number,
    user: "user",
    content,
    timestamp: now,
    type: MessageTypeEnum.ANSWER,
  };

  return new Message({
    id: nanoid(22),
    table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
    created_at: now,
    updated_at: now,
    data: {
      ...question.data,
      source_ref: { name: pixanoSource.table_info.name, id: pixanoSource.id },
      choices: [],
      ...messageData,
    },
  });
};
