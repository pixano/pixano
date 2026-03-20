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
  type InferenceModelSelection,
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
      (m) => m.task === ImageTask.SEGMENTATION || m.task === VideoTask.TRACKING,
    );
  },
};

export const vqaModels = {
  get value() {
    return inferenceServerStore.value.models.filter(
      (m) => m.task === MultimodalImageNLPTask.VLM,
    );
  },
};

export const selectedSegmentationModel = reactiveStore<InferenceModelSelection | null>(null);
export const selectedVqaModel = reactiveStore<InferenceModelSelection | null>(null);

// ─── Pixano Segmentation Inference ──────────────────────────────────────────────

export const pixanoInferenceSegmentationModelsStore = reactiveStore<
  PixanoInferenceSegmentationModel[]
>([]);
export const pixanoInferenceToValidateTrackingMasks = reactiveStore<MaskSegmentationOutput[]>([]);
export const pixanoInferenceTrackingNbAdditionalFrames = reactiveStore<number>(5);
export const pixanoInferenceTracking = reactiveStore<PixanoInferenceTrackingCfg>({
  mustValidate: false,
  validated: false,
});
