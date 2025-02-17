/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { BaseSchema, Message, MessageTypeEnum, type SaveItem } from "@pixano/core";
import type { UpdatedMessageEvent } from "@pixano/vqa-canvas/src/lib/types";

import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createUpdatedAnswer } from "../../utils/createUpdatedAnswer";
import { annotations, messages as messagesStore, saveData } from "../datasetItemWorkspaceStores";

export const updateMessageContent = (detail: UpdatedMessageEvent) => {
  const { answerId, content } = detail;

  const messages = get<Message[]>(messagesStore);
  const prevAnswer = messages.find(
    (message) => message.data.type === MessageTypeEnum.ANSWER && message.id === answerId,
  );

  if (!prevAnswer) {
    return;
  }

  const updatedMessage = createUpdatedAnswer({ prevAnswer, content });

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
