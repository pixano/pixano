/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

export type PixanoInferenceSegmentationModel = {
  selected: boolean;
  name: string;
};

export const pixanoInferenceSegmentationModelsStore = writable<PixanoInferenceSegmentationModel[]>(
  [],
);
