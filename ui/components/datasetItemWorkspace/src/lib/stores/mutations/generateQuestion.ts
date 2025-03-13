/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import {
  api,
  BaseSchema,
  MessageTypeEnum,
  QuestionTypeEnum,
  type CondititionalGenerationTextImageInput,
} from "@pixano/core";

import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { completionModelsStore } from "../../../../../vqaCanvas/src/stores/completionModels";
import { createNewMessage } from "../../utils/createNewMessage";
import { removeFieldFromObject } from "../../utils/removeUiFieldFromObject";
import { conversations, messages } from "../datasetItemWorkspaceStores";

export const generateQuestion = async (
  completionModel: string,
): Promise<{ content: string; choices: string[] } | null> => {
  const [conversation] = get(conversations);
  const prompt =
    get(completionModelsStore).find((m) => m.selected)?.prompts[MessageTypeEnum.QUESTION][
      QuestionTypeEnum.OPEN
    ] ?? "";
  const temperature = get(completionModelsStore).find((m) => m.selected)?.temperature ?? 1.0;

  if (conversation === undefined) {
    // There is no conversation on this item to link the message to
    return null;
  }

  const lastMessageOfConversation = get(messages).sort((a, b) => b.data.number - a.data.number)[0];

  const systemMessage = createNewMessage({
    item_ref: conversation.data.item_ref,
    view_ref: conversation.data.view_ref,
    entity_ref: { name: BaseSchema.Conversation, id: conversation.id },
    type: MessageTypeEnum.QUESTION,
    question_type: QuestionTypeEnum.OPEN,
    user: "user",
    inference_metadata: {},
    choices: [],
    number: lastMessageOfConversation ? lastMessageOfConversation.data.number + 1 : 0,
    content: prompt,
  });

  const input: CondititionalGenerationTextImageInput = {
    dataset_id: get(currentDatasetStore).id,
    conversation: removeFieldFromObject(conversation, "ui"),
    messages: [removeFieldFromObject(systemMessage, "ui")],
    model: completionModel,
    temperature,
    //TODO image_regex: ??
  };

  try {
    const generatedQuestion = await api.conditional_generation_text_image(input);

    if (!generatedQuestion) {
      return null;
    }

    return { content: generatedQuestion.data.content, choices: [] };
  } catch (err) {
    console.error("Model generation error:", err);
    return null;
  }
};
