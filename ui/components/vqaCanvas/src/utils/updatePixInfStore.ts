/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type ModelList, type PixanoInferenceInfo, type SystemPrompt } from "@pixano/core";

export function updatedPixanoInferenceStore(
  inputList: ModelList[],
  storedList: PixanoInferenceInfo[],
  defaultPrompts: SystemPrompt[],
) {
  const inputKeys = new Set(inputList.map((item) => `${item.name}-${item.task}`));
  const filteredList = storedList.filter((item) => inputKeys.has(`${item.name}-${item.task}`));
  const existingItems = new Set(filteredList.map((item) => `${item.name}-${item.task}`));
  const newItems = inputList
    .filter((item) => !existingItems.has(`${item.name}-${item.task}`))
    .map((item) => ({
      ...item,
      selected: false,
      prompts: defaultPrompts,
    }));

  return [...filteredList, ...newItems];
}
