/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  MessageGenerationPrompts,
  PixanoInferenceCompletionModel,
} from "$lib/stores/vqaStores.svelte";
import type { InferenceModelSelection } from "$lib/types/inference";
import { getInferenceModelKey } from "$lib/types/inference";

export function mergeModelLists(
  newModels: InferenceModelSelection[],
  existingModels: PixanoInferenceCompletionModel[],
  defaultPrompts: MessageGenerationPrompts,
  default_temperature: number,
): PixanoInferenceCompletionModel[] {
  const existingModelsMap = new Map(
    existingModels.map((model) => [getInferenceModelKey(model), model]),
  );

  return newModels.map(
    (model) =>
      existingModelsMap.get(getInferenceModelKey(model)) ?? {
        ...model,
        selected: false,
        prompts: defaultPrompts,
        temperature: default_temperature,
      },
  );
}
