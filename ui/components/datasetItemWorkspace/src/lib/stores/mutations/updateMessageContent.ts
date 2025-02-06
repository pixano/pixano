/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Message, type SaveItem } from "@pixano/core";
import type { UpdatedMessageEvent } from "@pixano/vqa-canvas/src/lib/types";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createUpdatedMessage } from "../../utils/createUpdatedMessage";
import { annotations, messages, saveData } from "../datasetItemWorkspaceStores";

export const updateMessageContent = (detail: UpdatedMessageEvent) => {
  const { answerId, content, answers, explanations } = detail;
  let prevMessage: Message | undefined;

  messages.subscribe((messages) => {
    prevMessage = messages.find((message) => message.id === answerId);
  });

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
