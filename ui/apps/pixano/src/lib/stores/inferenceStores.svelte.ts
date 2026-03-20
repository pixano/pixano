/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  MaskSegmentationOutput,
  PixanoInferenceSegmentationModel,
  PixanoInferenceTrackingCfg,
} from "$components/inference/segmentation/inference";

import { reactiveStore } from "./reactiveStore.svelte";
import {
  ImageTask,
  MultimodalImageNLPTask,
  VideoTask,
  type InferenceServerState,
} from "$lib/types/inference";

// ─── Inference Server ───────────────────────────────────────────────────────────

export const inferenceServerStore = reactiveStore<InferenceServerState>({
  connected: false,
  providers: [],
  defaultProvider: null,
  models: [],
  isLoading: false,
});

export const segmentationModels = {
  get value() {
    return inferenceServerStore.value.models.filter(
      (m) => m.task === ImageTask.MASK_GENERATION || m.task === VideoTask.MASK_GENERATION,
    );
  },
};

export const vqaModels = {
  get value() {
    return inferenceServerStore.value.models.filter(
      (m) => m.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION,
    );
  },
};

export const selectedSegmentationModelName = reactiveStore<string | null>(null);
export const selectedVqaModelName = reactiveStore<string | null>(null);

// ─── Pixano Segmentation Inference ──────────────────────────────────────────────

const DEFAULT_SEG_URL = "http://pixano-inference-sami:8000";
const DEFAULT_TRACK_URL = "http://pixano-inference-samv:8000";

export const pixanoInferenceSegmentationModelsStore = reactiveStore<
  PixanoInferenceSegmentationModel[]
>([]);
export const pixanoInferenceSegmentationURL = reactiveStore<string>(DEFAULT_SEG_URL);
export const pixanoInferenceTrackingURL = reactiveStore<string>(DEFAULT_TRACK_URL);
export const pixanoInferenceToValidateTrackingMasks = reactiveStore<MaskSegmentationOutput[]>([]);
export const pixanoInferenceTrackingNbAdditionalFrames = reactiveStore<number>(5);
export const pixanoInferenceTracking = reactiveStore<PixanoInferenceTrackingCfg>({
  mustValidate: false,
  validated: false,
});
