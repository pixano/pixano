/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MessageTypeEnum, type Message, type SaveItem } from "@pixano/core";
import type { NewAnswerEvent } from "@pixano/vqa-canvas/src/lib/types";
import { get } from "svelte/store";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewAnswer } from "../../utils/createNewAnswer";
import { annotations, messages as messagesStore, saveData } from "../datasetItemWorkspaceStores";

export const addAnswer = (detail: NewAnswerEvent) => {
  const { questionId, content } = detail;

  const messages = get<Message[]>(messagesStore);
  const question = messages.find(
    (message) => message.data.type === MessageTypeEnum.QUESTION && message.id === questionId,
  );

  if (!question) {
    return;
  }

  const newMessage = createNewAnswer({
    question,
    content,
  });

  annotations.update((prevAnnotations) => [...prevAnnotations, newMessage]);

  const save_item: SaveItem = {
    change_type: "add",
    object: newMessage,
  };

  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
};
