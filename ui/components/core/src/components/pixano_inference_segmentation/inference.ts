/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

import type { AnnotationType, MaskType } from "../../lib/types";

const DEFAULT_URL = "http://localhost:9152";

export type PixanoInferenceSegmentationModel = {
  selected: boolean;
  name: string;
};

export type PixanoInferenceSegmentationOutput = {
  mask: {
    id: string;
    created_at: string;
    updated_at: string;
    table_info: {
      name: string;
      group: string;
      base_schema: string;
    };
    data: MaskType & AnnotationType;
  };
};

export const pixanoInferenceSegmentationModelsStore = writable<PixanoInferenceSegmentationModel[]>(
  [],
);
export const pixanoInferenceSegmentationURL = writable<string>(DEFAULT_URL);
