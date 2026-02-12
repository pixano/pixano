/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { Message, MessageTypeEnum, type SaveItem } from "@pixano/core";
import type { DeleteQuestionEvent } from "@pixano/vqa-canvas/src/features/annotateItem/types";

import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { annotations, saveData } from "../datasetItemWorkspaceStores";

export const deleteQuestion = ({ questionId }: DeleteQuestionEvent) => {
  const allAnnotations = get(annotations);

  const question = allAnnotations.find(
    (a) => a.id === questionId && a instanceof Message && a.data.type === MessageTypeEnum.QUESTION,
  ) as Message | undefined;

  if (!question) {
    console.error("ERROR: Question not found for deletion", questionId);
    return;
  }

  const questionNumber = question.data.number;

  // Find all messages (question + answers) with the same number
  const messagesToDelete = allAnnotations.filter(
    (a) => a instanceof Message && a.data.number === questionNumber,
  );

  const idsToDelete = new Set(messagesToDelete.map((m) => m.id));

  // Remove from annotations store
  annotations.update((prev) => prev.filter((a) => !idsToDelete.has(a.id)));

  // Create SaveItem entries with change_type "delete" for each removed message
  for (const message of messagesToDelete) {
    const saveItem: SaveItem = {
      change_type: "delete",
      object: message,
    };
    saveData.update((current) => addOrUpdateSaveItem(current, saveItem));
  }
};
