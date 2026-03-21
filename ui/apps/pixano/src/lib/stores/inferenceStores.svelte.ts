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
  isSameInferenceModel,
  type InferenceModelSelection,
  type InferenceModel,
  type InferenceServerState,
} from "$lib/types/inference";
import { WorkspaceType } from "$lib/types/dataset";
import { itemMetas } from "$lib/stores/workspaceStores.svelte";

// ─── Inference Server ───────────────────────────────────────────────────────────

export const inferenceServerStore = reactiveStore<InferenceServerState>({
  connected: false,
  providers: [],
  defaultProvider: null,
  models: [],
  isLoading: false,
});

const STATIC_SEGMENTATION_MODEL_STORAGE_KEY = "pixano-static-segmentation-model";
const VIDEO_SEGMENTATION_MODEL_STORAGE_KEY = "pixano-video-segmentation-model";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function readStoredSelection(storageKey: string): InferenceModelSelection | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      "name" in parsed &&
      "provider_name" in parsed &&
      typeof parsed.name === "string" &&
      typeof parsed.provider_name === "string"
    ) {
      return {
        name: parsed.name,
        provider_name: parsed.provider_name,
      };
    }
  } catch {
    // Ignore malformed local storage entries.
  }

  return null;
}

function writeStoredSelection(
  storageKey: string,
  selection: InferenceModelSelection | null,
): void {
  if (!isBrowser()) return;
  if (!selection) {
    window.localStorage.removeItem(storageKey);
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(selection));
}

function toSelection(model: InferenceModel): InferenceModelSelection {
  return {
    name: model.name,
    provider_name: model.provider_name,
  };
}

function reconcileSegmentationSelection(
  availableModels: InferenceModel[],
  currentSelection: InferenceModelSelection | null,
): InferenceModelSelection | null {
  if (currentSelection) {
    const matched = availableModels.find((model) =>
      isSameInferenceModel(currentSelection, toSelection(model)),
    );
    if (matched) {
      return toSelection(matched);
    }
  }

  const fallback = availableModels[0];
  return fallback ? toSelection(fallback) : null;
}

function hasSameSelection(
  left: InferenceModelSelection | null,
  right: InferenceModelSelection | null,
): boolean {
  if (left === null && right === null) return true;
  return isSameInferenceModel(left, right);
}

export const staticSegmentationModels = {
  get value() {
    return inferenceServerStore.value.models.filter(
      (m) => m.task === ImageTask.SEGMENTATION,
    );
  },
};

export const videoSegmentationModels = {
  get value() {
    return inferenceServerStore.value.models.filter((m) => m.task === VideoTask.TRACKING);
  },
};

export const vqaModels = {
  get value() {
    return inferenceServerStore.value.models.filter(
      (m) => m.task === MultimodalImageNLPTask.VLM,
    );
  },
};

export const selectedStaticSegmentationModel = reactiveStore<InferenceModelSelection | null>(
  readStoredSelection(STATIC_SEGMENTATION_MODEL_STORAGE_KEY),
);
export const selectedVideoSegmentationModel = reactiveStore<InferenceModelSelection | null>(
  readStoredSelection(VIDEO_SEGMENTATION_MODEL_STORAGE_KEY),
);
export const selectedVqaModel = reactiveStore<InferenceModelSelection | null>(null);

export const currentSegmentationModels = {
  get value() {
    return itemMetas.value?.type === WorkspaceType.VIDEO
      ? videoSegmentationModels.value
      : staticSegmentationModels.value;
  },
};

export const currentSegmentationModel = {
  get value() {
    return itemMetas.value?.type === WorkspaceType.VIDEO
      ? selectedVideoSegmentationModel.value
      : selectedStaticSegmentationModel.value;
  },
  set value(selection: InferenceModelSelection | null) {
    if (itemMetas.value?.type === WorkspaceType.VIDEO) {
      selectedVideoSegmentationModel.value = selection;
      return;
    }
    selectedStaticSegmentationModel.value = selection;
  },
};

$effect.root(() => {
  $effect(() => {
    const availableModels = staticSegmentationModels.value;
    const currentSelection = selectedStaticSegmentationModel.value;
    const nextSelection = reconcileSegmentationSelection(availableModels, currentSelection);
    if (!hasSameSelection(currentSelection, nextSelection)) {
      selectedStaticSegmentationModel.value = nextSelection;
      return;
    }
    writeStoredSelection(STATIC_SEGMENTATION_MODEL_STORAGE_KEY, nextSelection);
  });
});

$effect.root(() => {
  $effect(() => {
    const availableModels = videoSegmentationModels.value;
    const currentSelection = selectedVideoSegmentationModel.value;
    const nextSelection = reconcileSegmentationSelection(availableModels, currentSelection);
    if (!hasSameSelection(currentSelection, nextSelection)) {
      selectedVideoSegmentationModel.value = nextSelection;
      return;
    }
    writeStoredSelection(VIDEO_SEGMENTATION_MODEL_STORAGE_KEY, nextSelection);
  });
});

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
