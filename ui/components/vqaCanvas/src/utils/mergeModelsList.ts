/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  MessageGenerationPrompts,
  PixanoInferenceCompletionModel,
} from "../stores/completionModels";

export function mergeModelLists(
  newModelsName: string[],
  existingModels: PixanoInferenceCompletionModel[],
  defaultPrompts: MessageGenerationPrompts,
): PixanoInferenceCompletionModel[] {
  const existingModelsMap = new Map(existingModels.map((model) => [model.name, model]));

  return newModelsName.map(
    (model) =>
      existingModelsMap.get(model) ?? {
        name: model,
        selected: false,
        prompts: defaultPrompts,
      },
  );
}
