/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

import type { MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";

export interface PixanoInferenceCompletionModel {
  selected: boolean;
  name: string;
  prompts: MessageGenerationPrompts;
  regex: MessageGenerationRegex;
}

export type MessageGenerationPrompts = {
  [key in MessageTypeEnum]: PromptByQuestionType;
} & { as_system: boolean };

export type MessageGenerationRegex = {
  image: string;
  object: string;
};

export type PromptByQuestionType = Record<QuestionTypeEnum, string>;

export const completionModelsStore = writable<PixanoInferenceCompletionModel[]>([]);
