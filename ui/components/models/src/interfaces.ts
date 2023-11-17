/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Imports
import { Tensor } from "onnxruntime-web";

import type { MaskRLE, MaskSVG } from "@pixano/core/src/interfaces";

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
  rle: MaskRLE;
  masks?: Tensor;
}

export interface InteractiveImageSegmenter {
  segmentImage(input: InteractiveImageSegmenterInput): Promise<SegmentationResult>;
  reset(): void;
}

export interface InteractiveImageSegmenterOutput {
  id: string;
  viewId: string;
  label: string;
  catId: number;
  output: SegmentationResult; //??? or already transformed polygon ????
  input_points: Array<LabeledClick>;
  input_box: Box;
  validated: boolean;
}
