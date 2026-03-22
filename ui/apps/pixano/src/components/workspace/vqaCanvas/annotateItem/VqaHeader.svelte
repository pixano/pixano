<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Cpu, Gear } from "phosphor-svelte";
  import { untrack } from "svelte";

  import ConfigurePromptModal from "../manageModels/ConfigurePromptModal.svelte";
  import { selectedVqaModel } from "$lib/stores/inferenceStores.svelte";
  import type { PixanoInferenceCompletionModel } from "$lib/stores/vqaStores.svelte";
  import {
    formatInferenceProviderName,
    getInferenceModelKey,
    type InferenceModel,
    type InferenceServerState,
  } from "$lib/types/inference";
  import { IconButton } from "$lib/ui";
  import { effectProbe } from "$lib/utils/effectProbe";

  interface Props {
    vqaSectionWidth: number;
    inferenceServer: InferenceServerState;
    vqaModels: InferenceModel[];
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
  }

  let {
    vqaSectionWidth,
    inferenceServer,
    vqaModels,
    completionModels,
    onCompletionModelsChange,
  }: Props = $props();

  let selectedModel = $state("");
  let showPromptModal = $state(false);

  let inferenceModels = $derived(
    vqaModels.map((m) => ({
      id: getInferenceModelKey(m),
      value: `${m.name} · ${formatInferenceProviderName(m.provider_name)}`,
      selection: { name: m.name, provider_name: m.provider_name },
    })),
  );

  $effect(() => {
    const model = selectedModel;
    const models = inferenceModels;
    untrack(() => {
      effectProbe("VqaHeader.syncSelectedModel", {
        selectedModel: model,
        modelCount: models.length,
      });
      if (!model) {
        selectedVqaModel.value = null;
        return;
      }
      let hasSelectionChange = false;
      const nextModels = completionModels.map((m) => {
        const shouldSelect = getInferenceModelKey(m) === model;
        if (m.selected === shouldSelect) return m;
        hasSelectionChange = true;
        return { ...m, selected: shouldSelect };
      });
      const selectedInferenceModel = models.find((entry) => entry.id === model)?.selection ?? null;
      selectedVqaModel.value = selectedInferenceModel;
      if (hasSelectionChange) onCompletionModelsChange?.(nextModels);
    });
  });

  $effect(() => {
    const models = inferenceModels;
    untrack(() => {
      effectProbe("VqaHeader.autoselect", {
        selectedModel,
        modelCount: models.length,
      });
      const hasSelection = models.some((model) => model.id === selectedModel);
      if (hasSelection) return;
      const currentSelection = selectedVqaModel.value;
      const currentSelectionId = currentSelection ? getInferenceModelKey(currentSelection) : "";
      selectedModel =
        models.find((model) => model.id === currentSelectionId)?.id ?? models[0]?.id ?? "";
    });
  });
</script>

<div class="h-16 px-4 border-b bg-card flex items-center justify-between shadow-sm z-10 shrink-0">
  <div class="flex items-center gap-3 overflow-hidden grow">
    <div class="p-2 bg-primary/10 rounded-lg text-primary shrink-0">
      <Cpu size={24} />
    </div>

    {#if !inferenceServer.connected}
      <span class="text-sm font-medium text-muted-foreground truncate">Server disconnected</span>
    {:else if inferenceModels.length === 0}
      <span class="text-sm font-medium text-muted-foreground truncate">No VLM models</span>
    {:else}
      <select
        class="bg-transparent border-none outline-none text-sm font-semibold text-foreground cursor-pointer truncate grow"
        bind:value={selectedModel}
      >
        {#each inferenceModels as { id, value }}
          <option value={id}>{value}</option>
        {/each}
      </select>
    {/if}
  </div>

  <div class="flex items-center gap-1">
    <IconButton
      tooltipContent="Model & Prompt Settings"
      disabled={completionModels.length === 0}
      onclick={() => (showPromptModal = !showPromptModal)}
    >
      <Gear weight="regular" size={24} />
    </IconButton>
  </div>
</div>

{#if showPromptModal}
  <ConfigurePromptModal
    {vqaSectionWidth}
    {completionModels}
    {onCompletionModelsChange}
    onCancelPrompt={() => (showPromptModal = false)}
  />
{/if}
