import * as ort from "onnxruntime-web";
// import * as ort from "onnxruntime-node";
import {
  InteractiveImageSegmenter,
  InteractiveImageSegmenterInput,
  LabeledClick,
  Box,
  SegmentationResult,
  LabeledPointsTensor,
} from "./interactive_image_segmentation";
import { maskDataToFortranArrayToRle } from "./mask_utils";
import { generatePolygonSegments, convertSegmentsToSVG } from "./tracer";

export class SAM implements InteractiveImageSegmenter {
  private onnxModel: ort.InferenceSession;

  private previousMask: ort.Tensor | null = null;

  // Image long side lenght
  imageLongSideLength: number = 1024;

  // prediction threshold
  predictionThreshold = 0.0;

  async init(modelWeights: ArrayBuffer | string) {
    this.onnxModel = await ort.InferenceSession.create(modelWeights);
    console.log("init sam model");
  }

  getScalingFactor(imageWidth: number, imageHeight: number) {
    return this.imageLongSideLength / Math.max(imageWidth, imageHeight);
  }

  getPreviousMask(): [ort.Tensor, ort.Tensor] {
    let maskInput: ort.Tensor;
    let hasMaskInput: ort.Tensor;

    if (this.previousMask) {
      maskInput = this.previousMask;
      hasMaskInput = new ort.Tensor("float32", [1]);
    } else {
      // There is no previous mask, so default to an empty tensor
      maskInput = new ort.Tensor(
        "float32",
        new Float32Array(256 * 256),
        [1, 1, 256, 256]
      );
      // There is no previous mask, so default to 0
      hasMaskInput = new ort.Tensor("float32", [0]);
    }

    return [maskInput, hasMaskInput];
  }

  /** Pre-process UI inputs before feeding them into SAM */
  preProcessInputs(
    clicks: Array<LabeledClick>,
    box: Box,
    imageWidth: number,
    imageHeight: number
  ): LabeledPointsTensor {
    const scale = this.getScalingFactor(imageWidth, imageHeight);

    // If there is no box input, a single padding point with
    // label -1 and coordinates (0.0, 0.0) should be concatenated
    // so initialize the array to support (n + 1) points.
    const n = clicks.length;
    //with a box: 2 more points; without: 1 for padding
    const num_additionalPoints = box ? 2 : 1;
    let pointCoords = new Float32Array(2 * (n + num_additionalPoints));
    let pointLabels = new Float32Array(n + num_additionalPoints);

    // Add clicks and scale to what SAM expects
    for (let i = 0; i < n; i++) {
      pointCoords[2 * i] = clicks[i].x * scale;
      pointCoords[2 * i + 1] = clicks[i].y * scale;
      pointLabels[i] = clicks[i].label;
    }

    if (box) {
      //topleft
      pointCoords[2 * n] = Math.min(box.x, box.x + box.width) * scale;
      pointCoords[2 * n + 1] = Math.min(box.y, box.y + box.height) * scale;
      pointLabels[n] = 2.0;
      // bottomright
      pointCoords[2 * n + 2] = Math.max(box.x, box.x + box.width) * scale;
      pointCoords[2 * n + 3] = Math.max(box.y, box.y + box.height) * scale;
      pointLabels[n + 1] = 3.0;
    } else {
      // Add in the extra point/label when only clicks and no box
      // The extra point is at (0, 0) with label -1
      pointCoords[2 * n] = 0.0;
      pointCoords[2 * n + 1] = 0.0;
      pointLabels[n] = -1.0;
    }

    const pointCoordsTensor = new ort.Tensor("float32", pointCoords, [
      1,
      n + num_additionalPoints,
      2,
    ]);
    const pointLabelsTensor = new ort.Tensor("float32", pointLabels, [
      1,
      n + num_additionalPoints,
    ]);

    return { points: pointCoordsTensor, labels: pointLabelsTensor };
  }

  async segmentImage(
    inputs: InteractiveImageSegmenterInput
  ): Promise<SegmentationResult> {
    const imageWidth = inputs.image.naturalWidth;
    const imageHeight = inputs.image.naturalHeight;
    const imageSizeTensor = new ort.Tensor("float32", [
      imageHeight,
      imageWidth,
    ]);
    const labeledPoints = this.preProcessInputs(
      inputs.points,
      inputs.box,
      imageWidth,
      imageHeight
    );
    const previousMask = this.getPreviousMask();

    const samInputs = {
      image_embeddings: inputs.embedding,
      point_coords: labeledPoints.points,
      point_labels: labeledPoints.labels,
      orig_im_size: imageSizeTensor,
      mask_input: previousMask[0],
      has_mask_input: previousMask[1],
    };

    console.log("RUN SAM PREDICTION");
    console.log("SAM inputs: ", samInputs);
    const results = await this.onnxModel.run(samInputs);
    const rleMask = maskDataToFortranArrayToRle(
      results.masks.data,
      imageHeight,
      imageWidth
    );
    const maskPolygons = generatePolygonSegments(rleMask, imageHeight);

    const masksSVG = convertSegmentsToSVG(maskPolygons);
    return {
      masksImageSVG: masksSVG,
      rle: { counts: rleMask, size: [imageHeight, imageWidth] },
      masks: results.mask, //note: actually we don't need this one
    };
  }

  inputNames(): Array<string> {
    return this.onnxModel.inputNames;
  }

  outputNames(): Array<string> {
    return this.onnxModel.outputNames;
  }

  reset() {
    this.previousMask = null;
  }
}
