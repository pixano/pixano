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
  prompts: AllPrompts;
}

export type AllPrompts = {
  question: GenerationSystemPrompts;
  answer: GenerationSystemPrompts;
  as_system: boolean;
};

export type GenerationSystemPrompts = Record<QuestionTypeEnum, string>;

export const completionModelsStore = writable<PixanoInferenceCompletionModel[]>([]);
