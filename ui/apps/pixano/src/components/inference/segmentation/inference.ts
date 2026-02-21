/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationData, BaseSchema, MaskData } from "$lib/types/dataset";

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
  data: MaskData & AnnotationData;
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
