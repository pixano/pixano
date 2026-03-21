<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, HardDrives, MagicWand } from "phosphor-svelte";

  import {
    inferenceServerStore,
    pixanoInferenceTracking,
    pixanoInferenceTrackingNbAdditionalFrames,
    selectedStaticSegmentationModel,
    selectedVideoSegmentationModel,
    staticSegmentationModels,
    videoSegmentationModels,
  } from "$lib/stores/inferenceStores.svelte";
  import { ensureInferenceRegistryLoaded } from "$lib/services/inferenceService";
  import { itemMetas } from "$lib/stores/workspaceStores.svelte";
  import { formatInferenceProviderName, getInferenceModelKey } from "$lib/types/inference";
  import { Checkbox, PrimaryButton, WorkspaceType } from "$lib/ui";

  interface Props {
    onConfirm?: () => void;
    onCancel?: () => void;
  }

  let { onConfirm, onCancel }: Props = $props();

  const isVideo = $derived(itemMetas.value?.type === WorkspaceType.VIDEO);
  const compatibleModels = $derived(
    isVideo ? videoSegmentationModels.value : staticSegmentationModels.value,
  );
  const currentSegmentationSelection = $derived(
    isVideo ? selectedVideoSegmentationModel.value : selectedStaticSegmentationModel.value,
  );

  let selectedModelKey = $state("");

  $effect(() => {
    void ensureInferenceRegistryLoaded();
  });

  $effect(() => {
    const availableModels = compatibleModels;
    const currentSelection = currentSegmentationSelection;
    const currentSelectionKey = currentSelection ? getInferenceModelKey(currentSelection) : "";
    const hasCurrentSelection = availableModels.some(
      (model) => getInferenceModelKey(model) === selectedModelKey,
    );
    if (hasCurrentSelection) return;
    if (currentSelectionKey) {
      selectedModelKey = currentSelectionKey;
      return;
    }
    selectedModelKey = availableModels[0] ? getInferenceModelKey(availableModels[0]) : "";
  });

  const handleSelect = (modelKey: string) => {
    selectedModelKey = modelKey;
  };

  const handleTrackingFramesChange = (nextValue: string) => {
    const parsed = Number.parseInt(nextValue, 10);
    pixanoInferenceTrackingNbAdditionalFrames.value = Number.isNaN(parsed)
      ? 0
      : Math.max(0, parsed);
  };

  const handleValTrackingClick = (checked: boolean) => {
    pixanoInferenceTracking.value = {
      mustValidate: checked,
      validated: false,
    };
  };

  function handleConfirm() {
    const selectedModel = compatibleModels.find(
      (model) => getInferenceModelKey(model) === selectedModelKey,
    );
    const selection = selectedModel
      ? {
          name: selectedModel.name,
          provider_name: selectedModel.provider_name,
        }
      : null;
    if (isVideo) {
      selectedVideoSegmentationModel.value = selection;
    } else {
      selectedStaticSegmentationModel.value = selection;
    }
    onConfirm?.();
  }

  function handleCancel() {
    onCancel?.();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={(event) => event.stopPropagation()}
  class="fixed top-[calc(64px+16px)] left-1/2 transform -translate-x-1/2 z-50
  rounded-2xl bg-card text-foreground flex flex-col gap-0 border border-border shadow-2xl w-[400px] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
>
  <div class="bg-primary/5 p-5 border-b border-border flex items-center gap-3">
    <div class="p-2 rounded-lg bg-primary/10">
      <MagicWand weight="regular" size={22} class="text-primary" />
    </div>
    <p class="font-bold text-sm tracking-tight">Smart Segmentation Model</p>
  </div>

  <div class="flex flex-col p-6 gap-6">
    {#if !inferenceServerStore.value.connected}
      <div class="flex flex-col items-center gap-4 py-4 text-center">
        <div class="p-3 rounded-full bg-muted/50">
          <HardDrives weight="regular" size={28} class="text-muted-foreground/50" />
        </div>
        <p class="text-xs text-muted-foreground leading-relaxed px-4">
          No inference server is connected. Register one from the home page to use AI models.
        </p>
      </div>
    {:else if compatibleModels.length === 0}
      <div class="flex flex-col items-center gap-4 py-4 text-center">
        <p class="text-xs text-muted-foreground font-medium">
          {isVideo ? "No tracking models found on server." : "No image segmentation models found on server."}
        </p>
      </div>
    {:else}
      <div class="space-y-2">
        <h4 class="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60 px-1">
          Available Models
        </h4>
        <div class="flex flex-col gap-2 max-h-[240px] overflow-y-auto pr-1">
          {#each compatibleModels as model}
            {@const modelKey = getInferenceModelKey(model)}
            <button
              class="flex flex-col gap-1 px-4 py-3 rounded-xl border text-left transition-all duration-200
              {selectedModelKey === modelKey
                ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                : 'border-border/60 bg-muted/20 hover:border-border hover:bg-muted/40'}"
              onclick={() => handleSelect(modelKey)}
            >
              <span
                class="text-xs font-bold {selectedModelKey === modelKey
                  ? 'text-primary'
                  : 'text-foreground'}"
              >
                {model.name}
              </span>
              <span class="text-[10px] text-muted-foreground font-medium italic opacity-70">
                via {formatInferenceProviderName(model.provider_name)}
              </span>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#if isVideo}
      <div class="h-px bg-border/40"></div>
      <div class="space-y-4">
        <div class="flex items-center justify-between px-1">
          <label for="tracking-frames-input" class="text-xs font-bold text-foreground/80">
            Tracking Window
          </label>
          <div
            class="flex items-center rounded-lg border border-border bg-muted/30 px-3 py-1.5 focus-within:ring-2 focus-within:ring-primary/20 transition-all"
          >
            <input
              id="tracking-frames-input"
              class="w-12 bg-transparent text-xs font-bold focus:outline-none text-center"
              type="number"
              min="0"
              step="1"
              value={pixanoInferenceTrackingNbAdditionalFrames.value}
              onchange={(event) => handleTrackingFramesChange(event.currentTarget.value)}
            />
            <span class="text-[10px] font-bold text-muted-foreground ml-1">frames</span>
          </div>
        </div>

        <div class="flex items-center gap-3 p-3 rounded-xl bg-muted/30 border border-border/40">
          <Checkbox.Root
            checked={pixanoInferenceTracking.value.mustValidate}
            onCheckedChange={handleValTrackingClick}
            class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
          >
            {#snippet children({ checked })}
              <span class="flex items-center justify-center text-current h-full w-full">
                {#if checked}
                  <Check class="h-3.5 w-3.5" />
                {/if}
              </span>
            {/snippet}
          </Checkbox.Root>
          <span class="text-xs font-medium text-foreground/80">Validate before tracking</span>
        </div>
      </div>
    {/if}

    <div class="flex flex-row gap-3 pt-2">
      <PrimaryButton onclick={handleCancel} class="flex-1 h-10">Cancel</PrimaryButton>
      <PrimaryButton
        onclick={handleConfirm}
        isSelected
        disabled={!selectedModelKey && compatibleModels.length > 0}
        class="flex-1 h-10"
      >
        Confirm
      </PrimaryButton>
    </div>
  </div>
</div>
