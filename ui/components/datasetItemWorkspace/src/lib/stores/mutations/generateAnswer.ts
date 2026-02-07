/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import {
  api,
  isQuestionData,
  QuestionTypeEnum,
  type CondititionalGenerationTextImageInput,
  type Message,
  type SaveItem,
} from "@pixano/core";
import { vqaModels } from "@pixano/core/src/lib/stores/inferenceStore";

import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { completionModelsStore } from "../../../../../vqaCanvas/src/stores/completionModels";
import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { removeFieldFromObject } from "../../utils/removeUiFieldFromObject";
import { annotations, conversations, saveData } from "../datasetItemWorkspaceStores";

export const generateAnswer = async (completionModel: string, question: Message) => {
  const questionData = question.data;
  const temperature = get(completionModelsStore).find((m) => m.selected)?.temperature ?? 1.0;

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

  const selectedVqa = get(vqaModels).find((m) => m.name === completionModel);
  const input: CondititionalGenerationTextImageInput = {
    dataset_id: get(currentDatasetStore).id,
    conversation: removeFieldFromObject(conversation, "ui"),
    messages: [removeFieldFromObject(question, "ui")],
    model: completionModel,
    temperature,
    provider_name: selectedVqa?.provider_name,
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
