/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Message, MessageTypeEnum, type SaveItem } from "@pixano/core";
import type { UpdatedMessageEvent } from "@pixano/vqa-canvas/src/lib/types";
import { get } from "svelte/store";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createUpdatedMessage } from "../../utils/createUpdatedMessage";
import { annotations, messages as messagesStore, saveData } from "../datasetItemWorkspaceStores";

export const updateMessageContent = (detail: UpdatedMessageEvent) => {
  const { answerId, content, answers, explanations } = detail;

  const messages = get<Message[]>(messagesStore);
  const prevMessage = messages.find(
    (message) => message.data.type === MessageTypeEnum.ANSWER && message.id === answerId,
  );

  if (!prevMessage) {
    return;
  }

  const updatedMessage = createUpdatedMessage({
    message: prevMessage,
    content,
    answers,
    explanations,
  });

  annotations.update((prevAnnotations) =>
    prevAnnotations.map((annotation) =>
      annotation.is_type(BaseSchema.Message) && annotation.id === answerId
        ? updatedMessage
        : annotation,
    ),
  );

  const save_item: SaveItem = {
    change_type: "update",
    object: updatedMessage,
  };

  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
};
