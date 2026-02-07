/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { derived, writable } from "svelte/store";

import { ImageTask, MultimodalImageNLPTask, VideoTask, type Task } from "../types";

export interface InferenceModel {
  name: string;
  task: Task;
  provider_name: string;
}

export interface ConnectedProvider {
  name: string;
  url: string | null;
}

export interface InferenceServerState {
  connected: boolean;
  providers: ConnectedProvider[];
  defaultProvider: string | null;
  models: InferenceModel[];
  isLoading: boolean;
}

export const inferenceServerStore = writable<InferenceServerState>({
  connected: false,
  providers: [],
  defaultProvider: null,
  models: [],
  isLoading: false,
});

export const segmentationModels = derived(inferenceServerStore, ($store) =>
  $store.models.filter(
    (m) => m.task === ImageTask.MASK_GENERATION || m.task === VideoTask.MASK_GENERATION,
  ),
);

export const vqaModels = derived(inferenceServerStore, ($store) =>
  $store.models.filter((m) => m.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION),
);

export const selectedSegmentationModelName = writable<string | null>(null);
export const selectedVqaModelName = writable<string | null>(null);
