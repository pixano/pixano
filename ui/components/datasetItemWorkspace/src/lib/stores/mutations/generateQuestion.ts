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
  type CondititionalGenerationTextImageInput,
} from "@pixano/core";

import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { createNewMessage } from "../../utils/createNewMessage";
import { conversations, messages } from "../datasetItemWorkspaceStores";

const prompt = `
  You have to formulate a QUESTION in relation to the given image <image 1>. 
  If you find it helpfull, you can get inspiration from the following metadata (as a JSON dict): 
`;

// const prompt = `
//   You have to formulate a QUESTION in relation to the given image <image 1>.
//   If you find it helpfull, you can get inspiration from the following metadata (as a JSON dict):
//   ${JSON.stringify(feats)}
// `;

export const generateQuestion = async (
  completionModel: string,
): Promise<{ content: string; choices: string[] } | null> => {
  const [conversation] = get(conversations);

  if (conversation === undefined) {
    // There is no conversation on this item to link the message to
    return null;
  }

  const lastMessageOfConversation = get(messages)
    .sort((a, b) => a.data.number - b.data.number) // Check order
    .pop();

  const systemMessage = createNewMessage({
    item_ref: conversation.data.item_ref,
    view_ref: conversation.data.view_ref,
    entity_ref: { name: BaseSchema.Conversation, id: conversation.id },
    type: MessageTypeEnum.SYSTEM,
    user: "system",
    inference_metadata: {},
    choices: [],
    number: lastMessageOfConversation ? lastMessageOfConversation.data.number + 1 : 0,
    content: prompt,
  });

  const input: CondititionalGenerationTextImageInput = {
    dataset_id: get(currentDatasetStore).id,
    conversation,
    messages: [systemMessage],
    model: completionModel,
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
