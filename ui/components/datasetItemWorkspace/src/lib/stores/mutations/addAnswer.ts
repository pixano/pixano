/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { MessageTypeEnum, type Message, type SaveItem } from "@pixano/core";
import type { NewAnswerEvent } from "@pixano/vqa-canvas/src/features/annotateItem/types";

import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewMessage } from "../../utils/createNewMessage";
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

  const newAnswer = createNewMessage({
    ...question.data,
    type: MessageTypeEnum.ANSWER,
    user: "user",
    inference_metadata: {},
    content,
    choices: [],
  });

  annotations.update((prevAnnotations) => [...prevAnnotations, newAnswer]);

  const save_item: SaveItem = {
    change_type: "add",
    object: newAnswer,
  };

  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
};
