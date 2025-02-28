/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import {
  api,
  BaseSchema,
  isQuestionData,
  MessageTypeEnum,
  QuestionTypeEnum,
  type CondititionalGenerationTextImageInput,
  type Message,
  type SaveItem,
} from "@pixano/core";

import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewMessage } from "../../utils/createNewMessage";
import { annotations, conversations, saveData } from "../datasetItemWorkspaceStores";

export const generateAnswer = async (completionModel: string, question: Message) => {
  const questionData = question.data;

  if (!isQuestionData(questionData)) {
    console.error("ERROR: Message is not a question");
    return;
  }

  if (question.data.question_type !== QuestionTypeEnum.OPEN) {
    console.warn("Sorry, generation is only available for Open questions for now.");
    return;
  }

  const [conversation] = get(conversations);

  if (conversation === undefined) {
    // There is no conversation on this item to link the message to
    return null;
  }

  const prompt = `
    You MUST add 'Dear Master,' at the beginning of your answer. This is VERY important and mandatory! 
    - and now the question: ${question.data.content}
  `;

  const systemMessage = createNewMessage({
    item_ref: conversation.data.item_ref,
    view_ref: conversation.data.view_ref,
    entity_ref: { name: BaseSchema.Conversation, id: conversation.id },
    type: MessageTypeEnum.SYSTEM,
    user: "system",
    inference_metadata: {},
    choices: [],
    number: question.data.number,
    content: prompt,
  });

  const input: CondititionalGenerationTextImageInput = {
    dataset_id: get(currentDatasetStore).id,
    conversation,
    messages: [question, systemMessage],
    model: completionModel,
  };

  try {
    const generatedAnswer = await api.conditional_generation_text_image(input);

    if (!generatedAnswer || !("data" in generatedAnswer)) {
      console.error(
        "Model generation error: Unexpected error, please look at Pixano-Inference logs for more information.",
      );
      return null;
    }

    annotations.update((prevAnnotations) => [...prevAnnotations, generatedAnswer]);

    const save_item: SaveItem = {
      change_type: "add",
      object: generatedAnswer,
    };

    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));

    return generatedAnswer;
  } catch {
    return null;
  }
};
