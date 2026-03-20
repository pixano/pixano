/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { Tensor } from "onnxruntime-web";

import type { MaskData, Reference } from "$lib/types/dataset";
import type { BoundingBox, LabeledClick } from "$lib/types/geometry";
import type { MaskBounds } from "$lib/utils/maskUtils";

export type { Tensor };

export interface LabeledPointsTensor {
  points: Tensor;
  labels: Tensor;
}

export interface InteractiveImageSegmenterInput {
  image: HTMLImageElement;
  embedding?: Tensor;
  points?: Array<LabeledClick>;
  box?: BoundingBox;
  mask?: Tensor;
}

export interface SegmentationResult {
  maskDataUrl: string;
  maskBounds?: MaskBounds;
  rle: MaskData;
  masks?: Tensor;
}

export interface InteractiveImageSegmenter {
  segmentImage(input: InteractiveImageSegmenterInput): Promise<SegmentationResult>;
  reset(): void;
}

export interface InteractiveImageSegmenterOutput {
  id: string;
  viewRef: Reference;
  label: string;
  output: SegmentationResult; //??? or already transformed polygon ????
  input_points: Array<LabeledClick>;
  input_box: BoundingBox;
  validated: boolean;
}
