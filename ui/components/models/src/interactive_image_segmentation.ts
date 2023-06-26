import { Tensor } from "onnxruntime-web";

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

export interface MaskRLE {
  counts: Array<number>;
  size: Array<number>;
}

export type MaskSVG = Array<string>;

export interface SegmentationResult {
  masksImageSVG: MaskSVG;
  rle: MaskRLE;
  masks?: Tensor;
}

export interface InteractiveImageSegmenter {
  segmentImage(
    input: InteractiveImageSegmenterInput
  ): Promise<SegmentationResult>;
  reset(): void;
}

export interface InteractiveImageSegmenterOutput {
  id: string;
  viewId: string;
  label: string;
  catID: number;
  output: SegmentationResult; //??? or already transformed polygon ????
  input_points: Array<LabeledClick>;
  input_box: Box;
  validated: boolean;
}
