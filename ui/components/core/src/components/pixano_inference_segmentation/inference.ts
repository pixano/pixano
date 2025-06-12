/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

import type { AnnotationType, BaseSchema, MaskType } from "../../lib/types";

const DEFAULT_SEG_URL = "http://pixano-inference-sami:8000";
const DEFAULT_TRACK_URL = "http://pixano-inference-samv:8000";

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

export type PixanoInferenceTrackingCfg = {
  mustValidate: boolean;
  validated: boolean;
};

export const pixanoInferenceSegmentationModelsStore = writable<PixanoInferenceSegmentationModel[]>(
  [],
);
export const pixanoInferenceSegmentationURL = writable<string>(DEFAULT_SEG_URL);
export const pixanoInferenceTrackingURL = writable<string>(DEFAULT_TRACK_URL);

export const pixanoInferenceToValidateTrackingMasks = writable<MaskSegmentationOutput[]>([]);

export const pixanoInferenceTrackingNbAdditionalFrames = writable<number>(5);

export const pixanoInferenceTracking = writable<PixanoInferenceTrackingCfg>({
  mustValidate: false,
  validated: false,
});
