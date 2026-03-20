/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveStore } from "./reactiveStore.svelte";
import type { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";

// ─── Types ──────────────────────────────────────────────────────────────────────

export interface PixanoInferenceCompletionModel {
  selected: boolean;
  name: string;
  prompts: MessageGenerationPrompts;
  temperature: number;
}

export type MessageGenerationPrompts = {
  [key in MessageTypeEnum]: PromptByQuestionType;
} & { as_system: boolean };

export type PromptByQuestionType = Record<QuestionTypeEnum, string>;

// ─── Store ──────────────────────────────────────────────────────────────────────

export const completionModelsStore = reactiveStore<PixanoInferenceCompletionModel[]>([]);
