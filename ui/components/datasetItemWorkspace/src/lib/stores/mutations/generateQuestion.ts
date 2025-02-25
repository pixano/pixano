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
  QuestionTypeEnum,
  type CondititionalGenerationTextImageInput,
  type Message,
} from "@pixano/core";

import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { entities, itemMetas } from "../datasetItemWorkspaceStores";

export const generateQuestion = async (completionModel: string): Promise<[string, string[]]> => {
  return new Promise((resolve, reject) => {
    let questionChoices: string[] = [];
    let questionContent: string = "";

    //TEST TMP: get dataset item metadata for a more dedicated question
    const all_feats = get(itemMetas).item.data;
    const { split, ...feats } = all_feats; // eslint-disable-line @typescript-eslint/no-unused-vars

    const conv: Conversation = get(entities).filter((e) =>
      e.is_type(BaseSchema.Conversation),
    )[0] as Conversation;

    //Prompt as fake Message to get a QUESTION --for convenience, we clone the first message and change the content
    let prompt: Message | null = null;
    const tmp_prompt = conv.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Message));
    if (tmp_prompt && tmp_prompt.length > 0) {
      const { ui, ...no_ui_ann } = tmp_prompt[0]; // eslint-disable-line @typescript-eslint/no-unused-vars
      prompt = structuredClone(no_ui_ann) as Message;
      // PROMPT --- TODO: make it user defined (with a default)
      prompt.data.content =
        "You have to formulate a QUESTION in relation to the given image <image 1>." +
        `If you find it helpfull, you can get inspiration from the following metadata (as a JSON dict): ${JSON.stringify(feats)}` +
        "Please also provide the expected answer.";
      prompt.data.question_type = QuestionTypeEnum.OPEN;
      prompt.data.choices = [];
      //prompt.data.content = `Please formulate a relevant question about the <image 1>`;
    }
    if (!prompt) {
      reject(new Error("Invalid prompt!"));
    } else {
      console.log("Prompt:", prompt?.data.content); //TMP DEV

      //requires to strip ui to avoir circular ref
      const { ui, ...conv_no_ui } = conv; // eslint-disable-line @typescript-eslint/no-unused-vars

      const input: CondititionalGenerationTextImageInput = {
        dataset_id: get(currentDatasetStore).id,
        conversation: conv_no_ui as Conversation,
        messages: [prompt],
        model: completionModel,
      };
      console.log("Model Input:", input); //TMP DEV
      api
        .conditional_generation_text_image(input)
        .then((ann) => {
          console.log("Model output: ", ann); //TMP DEV
          console.log(`Model answer: ${(ann as Message).data.content}`); //TMP DEV
          questionContent = (ann as Message).data.content;
          questionChoices = [];
          resolve([questionContent, questionChoices]);
        })
        .catch((err) => {
          console.error("Model generation error:", err);
          reject(new Error(err));
        });
    }
  });
};
