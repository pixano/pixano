/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MultimodalImageNLPTask, type MessageGenerationPrompts, type Model } from "../types";
import type {
  PixanoInferenceCompletionModel,
  PixanoInferenceMaskGenerationModel,
  PixanoInferenceModel,
} from "../types/inference/modelsStore";

export function mergeModelLists(
  newModels: Model[],
  existingModels: PixanoInferenceModel[],
  defaultPrompts: MessageGenerationPrompts | null,
  default_temperature: number,
): PixanoInferenceModel[] {
  const existingModelsMap = new Map(existingModels.map((model) => [model.name, model]));
  return newModels.map((model) => {
    if (existingModelsMap.get(model.name)) return existingModelsMap.get(model.name);
    if (model.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION) {
      return {
        ...model,
        selected: false,
        prompts: defaultPrompts,
        temperature: default_temperature,
      } as PixanoInferenceCompletionModel;
    } else {
      return {
        ...model,
        selected: false,
      } as PixanoInferenceMaskGenerationModel;
    }
  });
}
