/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { Tensor } from "onnxruntime-web";

import type { MaskSVG, MaskType, Reference } from "@pixano/core/src/lib/types/dataset";

export type { Tensor };

// Exports
export interface LabeledClick {
  x: number;
  y: number;
  label: number;
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LabeledPointsTensor {
  points: Tensor;
  labels: Tensor;
}

export interface InteractiveImageSegmenterInput {
  image: HTMLImageElement;
  embedding?: Tensor;
  points?: Array<LabeledClick>;
  box?: Box;
  mask?: Tensor;
}

export interface SegmentationResult {
  masksImageSVG: MaskSVG;
  rle: MaskType;
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
  input_box: Box;
  validated: boolean;
}
