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

function applyErrorState(): void {
  inferenceServerStore.value = {
    status: "error",
    connected: false,
    providers: [],
    defaultProvider: null,
    models: [],
  };
}

export async function loadInferenceRegistry(): Promise<void> {
  if (inferenceServerStore.value.status === "loading") return;

  inferenceServerStore.update((state) => ({ ...state, status: "loading" }));

  try {
    const registry = await getInferenceServers();
    const models = registry.connected ? await listInferenceModels() : [];
    inferenceServerStore.value = {
      status: "loaded",
      connected: registry.connected,
      providers: registry.providers,
      defaultProvider: registry.default_provider,
      models,
    };
  } catch {
    applyErrorState();
  }
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

// Auto-load inference registry on first module import.
// Follows the codebase pattern of $effect.root() at module level
// (see theme sync in appStores.svelte.ts, model reconciliation in inferenceStores.svelte.ts).
$effect.root(() => {
  $effect(() => {
    if (inferenceServerStore.value.status !== "idle") return;
    void loadInferenceRegistry();
  });
});
