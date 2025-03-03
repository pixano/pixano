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
  prompts: QuestionGenerationSystemPrompts;
}

export type QuestionGenerationSystemPrompts = Record<
  QuestionTypeEnum,
  {
    content: string;
    as_system: boolean;
  }
>;

export const completionModelsStore = writable<PixanoInferenceCompletionModel[]>([]);
