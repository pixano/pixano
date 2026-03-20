/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  connectToServer,
  getInferenceStatus,
  listAllModels,
  type ModelWithProvider,
} from "$lib/api/inferenceApi";
import { inferenceServerStore } from "$lib/stores/inferenceStores.svelte";
import type { InferenceModel } from "$lib/types/inference";

async function refreshModels(): Promise<InferenceModel[]> {
  const models: ModelWithProvider[] = await listAllModels();
  return models as InferenceModel[];
}

export async function checkInferenceStatus(): Promise<void> {
  inferenceServerStore.update((s) => ({ ...s, isLoading: true }));
  try {
    const status = await getInferenceStatus();
    if (status.connected) {
      const models = await refreshModels();
      inferenceServerStore.value = {
        connected: true,
        providers: status.providers,
        defaultProvider: status.default,
        models,
        isLoading: false,
      };
    } else {
      inferenceServerStore.value = {
        connected: false,
        providers: [],
        defaultProvider: null,
        models: [],
        isLoading: false,
      };
    }
  } catch {
    inferenceServerStore.value = {
      connected: false,
      providers: [],
      defaultProvider: null,
      models: [],
      isLoading: false,
    };
  }
}

export async function connectToInferenceServer(url: string): Promise<boolean> {
  const success = await connectToServer(url);
  if (success) {
    await checkInferenceStatus();
  }
  return success;
}

export async function refreshInferenceModels(): Promise<void> {
  try {
    const models = await refreshModels();
    inferenceServerStore.update((s) => ({ ...s, models }));
  } catch {
    // keep existing state on error
  }
}
