/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";

/**
 * The slice of `/inference` the annotation tools need. Ported from
 * `ui/apps/pixano/src/lib/api/inferenceApi.ts`, trimmed to mask generation:
 * everything else (VLM, detection, video tracking, provider registration) has
 * no caller in this app yet, and D10 says to write the interface against a real
 * feature rather than pre-declare it.
 *
 * The heavy lifting stays server-side. The legacy UI also shipped an in-browser
 * ONNX SAM (`lib/models/Sam.ts` + `onnxruntime-web`); this app deliberately does
 * not, so there is one inference path to reason about instead of two.
 */

/** One model exposed by a connected provider, as `/models/list` returns it. */
export interface InferenceModel {
  name: string;
  task: string;
  provider_name: string;
}

/** Backend task name for the SAM-style prompt→mask models. */
export const MASK_GENERATION_TASK = "image_mask_generation";

/**
 * Models a connected provider offers, optionally narrowed to one task. Returns
 * an empty list when nothing is connected — the backend answers `[]` rather
 * than erroring, so "no provider" and "provider with no models" look the same
 * to callers, which is what they should do about it anyway.
 */
export async function listInferenceModels(task?: string): Promise<InferenceModel[]> {
  const qs = task ? `?task=${encodeURIComponent(task)}` : "";
  return requestJson<InferenceModel[]>(
    `/inference/models/list${qs}`,
    { headers: JSON_HEADERS, method: "GET" },
    "listInferenceModels",
  );
}

/** A mask as the inference server returns it: the CompressedRLE pair. */
export interface InferenceMask {
  /** `[height, width]` of the grid the RLE indexes into. */
  size: [number, number];
  /** COCO run-length encoding; the server decodes the bytes to utf-8 for us. */
  counts: string;
}

/**
 * Prompts for one segmentation. Coordinates are in the **image's own pixel
 * grid**, not display pixels — the server runs the model on the stored image.
 */
export interface MaskPrompt {
  /** `[x, y]` per point. */
  points: [number, number][];
  /** 1 for "include this", 0 for "exclude this"; one per point. */
  labels: (0 | 1)[];
  /** Optional `[x1, y1, x2, y2]` box narrowing the region. */
  box?: [number, number, number, number];
}

export interface GenerateImageMaskRequest {
  model: string;
  datasetId: string;
  viewId: string;
  prompt: MaskPrompt;
}

interface ImageMaskGenerationResponse {
  data?: {
    masks?: InferenceMask[][];
  };
}

/**
 * Run one prompt through a mask-generation model and return the masks it
 * proposed, best-first.
 *
 * The wire format nests masks per prompt batch (`masks[batch][candidate]`);
 * we send a single batch, so the first row is the one that matters. Asking for
 * a single output keeps the choice out of the UI until there is somewhere to
 * present alternatives.
 */
export async function generateImageMask(
  request: GenerateImageMaskRequest,
): Promise<InferenceMask[]> {
  const body = {
    model: request.model,
    dataset_id: request.datasetId,
    view_id: request.viewId,
    points: [request.prompt.points.map(([x, y]) => [Math.round(x), Math.round(y)])],
    labels: [request.prompt.labels],
    boxes: request.prompt.box ? [request.prompt.box.map((v) => Math.round(v))] : null,
    num_multimask_outputs: 1,
    multimask_output: false,
    return_image_embedding: false,
    return_logits: false,
  };

  const res = await requestJson<ImageMaskGenerationResponse>(
    "/inference/image_mask_generation",
    { headers: JSON_HEADERS, method: "POST", body: JSON.stringify(body) },
    "generateImageMask",
  );
  return res.data?.masks?.[0] ?? [];
}
