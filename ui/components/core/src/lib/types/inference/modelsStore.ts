/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

import type {
  ImageTask,
  MessageGenerationPrompts,
  MultimodalImageNLPTask,
  Task,
} from "./inference";

export type PixanoInferenceModelBase = {
  selected: boolean;
  name: string;
  task: Task;
};

// NLP Completion //
export type PixanoInferenceCompletionModel = PixanoInferenceModelBase & {
  prompts: MessageGenerationPrompts;
  temperature: number;
  task: MultimodalImageNLPTask.CONDITIONAL_GENERATION;
};

// IMAGE Mask Generation //
export type PixanoInferenceMaskGenerationModel = PixanoInferenceModelBase & {
  task: ImageTask.MASK_GENERATION;
};

export type PixanoInferenceModel =
  | PixanoInferenceCompletionModel
  | PixanoInferenceMaskGenerationModel;

export const pixanoInferenceModelsStore = writable<PixanoInferenceModel[]>([]);
