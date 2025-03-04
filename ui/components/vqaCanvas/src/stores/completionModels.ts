/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

import type { QuestionTypeEnum } from "@pixano/core";

export interface PixanoInferenceCompletionModel {
  selected: boolean;
  name: string;
  prompts: MessageGenerationPrompts;
}

export type MessageGenerationPrompts = {
  question: PromptByQuestionType;
  answer: PromptByQuestionType;
  as_system: boolean;
};

export type PromptByQuestionType = Record<QuestionTypeEnum, string>;

export const completionModelsStore = writable<PixanoInferenceCompletionModel[]>([]);
