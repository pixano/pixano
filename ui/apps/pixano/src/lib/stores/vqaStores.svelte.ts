/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveStore } from "./reactiveStore.svelte";
import type { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";
import type { InferenceModelSelection } from "$lib/types/inference";

// ─── Types ──────────────────────────────────────────────────────────────────────

export interface PixanoInferenceCompletionModel extends InferenceModelSelection {
  selected: boolean;
  prompts: MessageGenerationPrompts;
  temperature: number;
}

export type MessageGenerationPrompts = {
  [key in MessageTypeEnum]: PromptByQuestionType;
} & { as_system: boolean };

export type PromptByQuestionType = Record<QuestionTypeEnum, string>;

// ─── Store ──────────────────────────────────────────────────────────────────────

export const completionModelsStore = reactiveStore<PixanoInferenceCompletionModel[]>([]);
