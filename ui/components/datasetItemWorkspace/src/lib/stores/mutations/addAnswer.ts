/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Message, SaveItem } from "@pixano/core";
import type { NewAnswerEvent } from "@pixano/vqa-canvas/src/lib/types";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewAnswer } from "../../utils/createNewAnswer";
import { annotations, messages, saveData } from "../datasetItemWorkspaceStores";

export const addAnswer = (detail: NewAnswerEvent) => {
  const { questionId, content, answers, explanations } = detail;

  let question: Message | undefined;

  messages.subscribe((messages) => {
    question = messages.find((message) => message.id === questionId);
  });

  if (!question) {
    return;
  }

  const newMessage = createNewAnswer({
    question,
    content,
    answers,
    explanations,
  });

  annotations.update((prevAnnotations) => [...prevAnnotations, newMessage]);

  const save_item: SaveItem = {
    change_type: "add",
    object: newMessage,
  };

  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
};
