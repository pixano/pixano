<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Server, Wand2Icon } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import { currentDatasetStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    inferenceServerStore,
    segmentationModels,
    selectedSegmentationModelName,
  } from "../../lib/stores/inferenceStore";
  import { WorkspaceType } from "../../lib/types";
  import Checkbox from "../ui/checkbox/checkbox.svelte";
  import PrimaryButton from "../ui/molecules/PrimaryButton.svelte";
  import {
    pixanoInferenceTracking,
    pixanoInferenceTrackingNbAdditionalFrames,
    type PixanoInferenceTrackingCfg,
  } from "./inference";

  const dispatch = createEventDispatcher();

  let isVideo = $currentDatasetStore?.workspace === WorkspaceType.VIDEO;

  // Initialize selected model from store if available
  let selectedModel = $selectedSegmentationModelName ?? ($segmentationModels[0]?.name || "");

  const handleSelect = (modelName: string) => {
    selectedModel = modelName;
  };

  const handleValTrackingClick = (checked: boolean) => {
    pixanoInferenceTracking.set({
      mustValidate: checked,
      validated: false,
    } as PixanoInferenceTrackingCfg);
  };

  function handleConfirm() {
    selectedSegmentationModelName.set(selectedModel || null);
    dispatch("confirm");
  }

  function handleCancel() {
    dispatch("cancel");
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(64px+16px)] left-1/2 transform -translate-x-1/2 z-50
  rounded-2xl bg-card text-foreground flex flex-col gap-0 border border-border shadow-2xl w-[400px] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
>
  <div class="bg-primary/5 p-5 border-b border-border flex items-center gap-3">
    <div class="p-2 rounded-lg bg-primary/10">
      <Wand2Icon size={18} class="text-primary" />
    </div>
    <p class="font-bold text-sm tracking-tight">Smart Segmentation Model</p>
  </div>

  <div class="flex flex-col p-6 gap-6">
    {#if !$inferenceServerStore.connected}
      <div class="flex flex-col items-center gap-4 py-4 text-center">
        <div class="p-3 rounded-full bg-muted/50">
          <Server size={24} class="text-muted-foreground/50" />
        </div>
        <p class="text-xs text-muted-foreground leading-relaxed px-4">
          Connect to an inference server from the toolbar to use AI models.
        </p>
      </div>
    {:else if $segmentationModels.length === 0}
      <div class="flex flex-col items-center gap-4 py-4 text-center">
        <p class="text-xs text-muted-foreground font-medium">
          No segmentation models found on server.
        </p>
      </div>
    {:else}
      <div class="space-y-2">
        <h4 class="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60 px-1">
          Available Models
        </h4>
        <div class="flex flex-col gap-2 max-h-[240px] overflow-y-auto pr-1">
          {#each $segmentationModels as model}
            <button
              class="flex flex-col gap-1 px-4 py-3 rounded-xl border text-left transition-all duration-200
              {selectedModel === model.name
                ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                : 'border-border/60 bg-muted/20 hover:border-border hover:bg-muted/40'}"
              on:click={() => handleSelect(model.name)}
            >
              <span
                class="text-xs font-bold {selectedModel === model.name
                  ? 'text-primary'
                  : 'text-foreground'}"
              >
                {model.name}
              </span>
              {#if model.provider_name}
                <span class="text-[10px] text-muted-foreground font-medium italic opacity-70">
                  via {model.provider_name.includes("@")
                    ? model.provider_name.substring(model.provider_name.indexOf("@") + 1)
                    : model.provider_name}
                </span>
              {/if}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#if isVideo}
      <div class="h-px bg-border/40" />
      <div class="space-y-4">
        <div class="flex items-center justify-between px-1">
          <label for="positiveInteger" class="text-xs font-bold text-foreground/80">
            Tracking Window
          </label>
          <div
            class="flex items-center rounded-lg border border-border bg-muted/30 px-3 py-1.5 focus-within:ring-2 focus-within:ring-primary/20 transition-all"
          >
            <input
              class="w-12 bg-transparent text-xs font-bold focus:outline-none text-center"
              type="number"
              id="positiveInteger"
              min="0"
              step="1"
              value={$pixanoInferenceTrackingNbAdditionalFrames}
              on:change={(e) => {
                pixanoInferenceTrackingNbAdditionalFrames.set(parseInt(e.currentTarget.value));
              }}
            />
            <span class="text-[10px] font-bold text-muted-foreground ml-1">frames</span>
          </div>
        </div>

        <div class="flex items-center gap-3 p-3 rounded-xl bg-muted/30 border border-border/40">
          <Checkbox
            handleClick={handleValTrackingClick}
            checked={$pixanoInferenceTracking.mustValidate}
          />
          <span class="text-xs font-medium text-foreground/80">Validate before tracking</span>
        </div>
      </div>
    {/if}

    <div class="flex flex-row gap-3 pt-2">
      <PrimaryButton on:click={handleCancel} class="flex-1 h-10">Cancel</PrimaryButton>
      <PrimaryButton
        on:click={handleConfirm}
        isSelected
        disabled={!selectedModel && $segmentationModels.length > 0}
        class="flex-1 h-10"
      >
        Confirm
      </PrimaryButton>
    </div>
  </div>
</div>
