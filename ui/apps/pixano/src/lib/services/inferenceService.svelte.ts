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

function applyErrorState(): void {
  inferenceServerStore.value = {
    status: "error",
    connected: false,
    providers: [],
    defaultProvider: null,
    models: [],
  };
  syncCompletionModels([]);
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

    const vlmModels = models.filter((m) => m.task === MultimodalImageNLPTask.VLM);
    syncCompletionModels(vlmModels);
  } catch {
    applyErrorState();
  }
}

let _registryLoadAttempted = false;

export async function ensureInferenceRegistryLoaded(): Promise<void> {
  const state = inferenceServerStore.value;
  if (state.status === "loading") return;
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

// Auto-load inference registry on first module import.
// Follows the codebase pattern of $effect.root() at module level
// (see theme sync in appStores.svelte.ts, model reconciliation in inferenceStores.svelte.ts).
$effect.root(() => {
  $effect(() => {
    if (inferenceServerStore.value.status !== "idle") return;
    void loadInferenceRegistry();
  });
});
