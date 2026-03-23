/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  getInferenceServers,
  listInferenceModels,
  registerInferenceServer,
} from "$lib/api/inferenceApi";
import { inferenceServerStore } from "$lib/stores/inferenceStores.svelte";
import { syncCompletionModels } from "$lib/stores/vqaStores.svelte";
import { MultimodalImageNLPTask } from "$lib/types/inference";

function applyDisconnectedState(): void {
  inferenceServerStore.value = {
    connected: false,
    providers: [],
    defaultProvider: null,
    models: [],
    isLoading: false,
  };
  syncCompletionModels([]);
}

export async function loadInferenceRegistry(): Promise<void> {
  if (inferenceServerStore.value.isLoading) return;

  inferenceServerStore.update((state) => ({ ...state, isLoading: true }));

  try {
    const registry = await getInferenceServers();
    const models = registry.connected ? await listInferenceModels() : [];
    inferenceServerStore.value = {
      connected: registry.connected,
      providers: registry.providers,
      defaultProvider: registry.default_provider,
      models,
      isLoading: false,
    };

    const vlmModels = models.filter((m) => m.task === MultimodalImageNLPTask.VLM);
    syncCompletionModels(vlmModels);
  } catch {
    applyDisconnectedState();
  }
}

let _registryLoadAttempted = false;

export async function ensureInferenceRegistryLoaded(): Promise<void> {
  const state = inferenceServerStore.value;
  if (state.isLoading) return;
  if (state.providers.length > 0 || state.models.length > 0) return;
  if (_registryLoadAttempted) return;
  _registryLoadAttempted = true;
  await loadInferenceRegistry();
}

export async function refreshInferenceModels(): Promise<void> {
  await loadInferenceRegistry();
}

export async function connectToInferenceServer(
  url: string | null,
  type: string = "pixano-inference",
  apiKey: string | null = null,
): Promise<{ success: true } | { success: false; error: string }> {
  const result = await registerInferenceServer(url, type, apiKey);
  if ("error" in result) {
    return { success: false, error: result.error };
  }

  await loadInferenceRegistry();
  return { success: true };
}
