/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { Tensor } from "onnxruntime-web";

import type { MaskSvgPaths, MaskData, Reference } from "$lib/types/dataset";

export type { Tensor };

// Exports
export interface SamLabeledClick {
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
  points?: Array<SamLabeledClick>;
  box?: Box;
  mask?: Tensor;
}

export interface SegmentationResult {
  masksImageSVG: MaskSvgPaths;
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
  input_points: Array<SamLabeledClick>;
  input_box: Box;
  validated: boolean;
}
