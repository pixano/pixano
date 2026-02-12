/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { Entity, Message, MessageTypeEnum, type SaveItem } from "@pixano/core";
import type { StoreQuestionEvent } from "@pixano/vqa-canvas/src/features/addQuestion/types";

import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewMessage } from "../../utils/createNewMessage";
import { annotations, messages as messagesStore, saveData } from "../datasetItemWorkspaceStores";

export const addQuestion = ({
  newQuestionData,
  parentEntity,
}: {
  newQuestionData: StoreQuestionEvent;
  parentEntity: Entity;
}) => {
  const messages = get<Message[]>(messagesStore);

  // In case a question was deleted
  // Find the number of the last question instead of using messages.length
  const newQuestionNumber =
    messages.length === 0 ? 0 : Math.max(...messages.map((m) => m.data.number)) + 1;

  const { labelFormat, ...questionData } = newQuestionData;

  const newQuestion = createNewMessage({
    ...questionData,
    number: newQuestionNumber,
    entity_ref: { id: parentEntity.id, name: parentEntity.table_info.name },
    view_ref: parentEntity.data.view_ref,
    item_ref: parentEntity.data.item_ref,
    type: MessageTypeEnum.QUESTION,
    user: "user",
    inference_metadata: {},
  });

  if (labelFormat) {
    (newQuestion.ui as Record<string, unknown>).labelFormat = labelFormat;
  }

  annotations.update((prevAnnotations) => [...prevAnnotations, newQuestion]);

  const save_item: SaveItem = {
    change_type: "add",
    object: newQuestion,
  };

  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
};
