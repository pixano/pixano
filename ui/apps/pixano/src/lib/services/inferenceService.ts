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

function applyDisconnectedState(): void {
  inferenceServerStore.value = {
    connected: false,
    providers: [],
    defaultProvider: null,
    models: [],
    isLoading: false,
  };
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
  } catch {
    applyDisconnectedState();
  }
}

export async function ensureInferenceRegistryLoaded(): Promise<void> {
  const state = inferenceServerStore.value;
  if (state.isLoading) return;
  if (state.providers.length > 0 || state.models.length > 0) return;
  await loadInferenceRegistry();
}

export async function refreshInferenceModels(): Promise<void> {
  await loadInferenceRegistry();
}

export async function connectToInferenceServer(url: string): Promise<boolean> {
  const connectedProvider = await registerInferenceServer(url);
  if (!connectedProvider) {
    return false;
  }

  await loadInferenceRegistry();
  return true;
}
