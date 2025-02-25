/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import {
  api,
  BaseSchema,
  Conversation,
  isQuestionData,
  type CondititionalGenerationTextImageInput,
  type Message,
  type SaveItem,
} from "@pixano/core";

import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewAnswer } from "../../utils/createNewAnswer";
import { annotations, entities, saveData } from "../datasetItemWorkspaceStores";

export const generateAnswer = (completionModel: string, question: Message) => {
  const questionData = question.data;

  if (!isQuestionData(questionData)) {
    console.error("ERROR: Message is not a question");
    return;
  }

  modelGeneration(completionModel, question)
    .then((answer) => {
      const newAnswer = createNewAnswer({ question, content: answer });

      annotations.update((prevAnnotations) => [...prevAnnotations, newAnswer]);
      const save_item: SaveItem = {
        change_type: "add",
        object: newAnswer,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    })
    .catch((err) => {
      console.error("Error while generating answer:", err);
    });
};

export const modelGeneration = async (
  completionModel: string,
  question: Message,
): Promise<string> => {
  return new Promise((resolve, reject) => {
    let answer: string;

    const conv: Conversation = get(entities).filter(
      (e) => e.is_type(BaseSchema.Conversation) && question.data.entity_ref.id === e.id,
    )[0] as Conversation;

    //requires to strip ui to avoir circular ref
    const { ui, ...conv_no_ui } = conv; // eslint-disable-line @typescript-eslint/no-unused-vars

    const input: CondititionalGenerationTextImageInput = {
      dataset_id: get(currentDatasetStore).id,
      conversation: conv_no_ui as Conversation,
      messages: [question],
      model: completionModel,
    };
    console.log("Model Input:", input); //TMP DEV
    api
      .conditional_generation_text_image(input)
      .then((ann) => {
        console.log("Model output: ", ann); //TMP DEV
        console.log(`Model answer: ${(ann as Message).data.content}`); //TMP DEV
        answer = (ann as Message).data.content;
        resolve(answer);
      })
      .catch((err) => {
        console.error("Model generation error:", err);
        reject(new Error(err));
      });
  });
};
