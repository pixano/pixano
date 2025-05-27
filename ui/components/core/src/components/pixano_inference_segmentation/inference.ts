/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

import type { AnnotationType, BaseSchema, MaskType } from "../../lib/types";

const DEFAULT_URL = "http://localhost:9152";

export type PixanoInferenceSegmentationModel = {
  selected: boolean;
  name: string;
};

export type MaskSegmentationOutput = {
  id: string;
  created_at: string;
  updated_at: string;
  table_info: {
    name: string;
    group: string;
    base_schema: BaseSchema;
  };
  data: MaskType & AnnotationType;
};

export type PixanoInferenceSegmentationOutput = {
  mask: MaskSegmentationOutput;
};

export type PixanoInferenceVideoSegmentationOutput = {
  masks: MaskSegmentationOutput[];
};

export const pixanoInferenceSegmentationModelsStore = writable<PixanoInferenceSegmentationModel[]>(
  [],
);
export const pixanoInferenceSegmentationURL = writable<string>(DEFAULT_URL);

export const pixanoInferenceToValidateTrackingMasks = writable<MaskSegmentationOutput[]>([]);
