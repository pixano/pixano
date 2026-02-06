/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { getInferenceStatus } from "../../api/inference/getInferenceStatus";
import { isInferenceApiHealthy } from "../../api/inference/isInferenceApiHealthy";
import { listModels } from "../../api/inference/listModels";
import { inferenceServerStore, type InferenceModel } from "../stores/inferenceStore";

async function refreshModels(): Promise<InferenceModel[]> {
  const models = await listModels();
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
        url: status.url,
        models,
        isLoading: false,
      });
    } else {
      inferenceServerStore.set({
        connected: false,
        url: null,
        models: [],
        isLoading: false,
      });
    }
  } catch {
    inferenceServerStore.set({
      connected: false,
      url: null,
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
      const models = await refreshModels();
      inferenceServerStore.set({
        connected: true,
        url,
        models,
        isLoading: false,
      });
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

export async function refreshInferenceModels(): Promise<void> {
  try {
    const models = await refreshModels();
    inferenceServerStore.update((s) => ({ ...s, models }));
  } catch {
    // keep existing state on error
  }
}
