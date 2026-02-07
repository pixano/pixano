/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { disconnectProvider } from "../../api/inference/disconnectProvider";
import { getInferenceStatus } from "../../api/inference/getInferenceStatus";
import { isInferenceApiHealthy } from "../../api/inference/isInferenceApiHealthy";
import { listAllModels, type ModelWithProvider } from "../../api/inference/listAllModels";
import type { InferenceModel } from "../types";
import { inferenceServerStore } from "../stores/inferenceStore";

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
      inferenceServerStore.set({
        connected: true,
        providers: status.providers,
        defaultProvider: status.default,
        models,
        isLoading: false,
      });
    } else {
      inferenceServerStore.set({
        connected: false,
        providers: [],
        defaultProvider: null,
        models: [],
        isLoading: false,
      });
    }
  } catch {
    inferenceServerStore.set({
      connected: false,
      providers: [],
      defaultProvider: null,
      models: [],
      isLoading: false,
    });
  }
}

export async function connectToInferenceServer(url: string): Promise<boolean> {
  inferenceServerStore.update((s) => ({ ...s, isLoading: true }));
  try {
    const connected = await isInferenceApiHealthy(url);
    if (connected) {
      // Refresh full state from the server (additive — does not replace existing providers)
      await checkInferenceStatus();
      return true;
    } else {
      inferenceServerStore.update((s) => ({ ...s, isLoading: false }));
      return false;
    }
  } catch {
    inferenceServerStore.update((s) => ({ ...s, isLoading: false }));
    return false;
  }
}

export async function disconnectFromProvider(name: string): Promise<boolean> {
  const success = await disconnectProvider(name);
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
