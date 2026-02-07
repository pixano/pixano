<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
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
  class="fixed top-[calc(80px+5px)] left-1/2 transform -translate-x-1/2 z-50
  rounded-md bg-card text-foreground flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Select a Mask Generation Model</p>
  </div>
  <div class="flex flex-col p-3 gap-5">
    {#if !$inferenceServerStore.connected}
      <p class="text-sm text-muted-foreground py-2">
        Connect to an inference server from the toolbar to use models.
      </p>
    {:else if $segmentationModels.length === 0}
      <p class="text-muted-foreground text-sm">No segmentation models available on the server.</p>
    {:else}
      <div class="flex flex-col gap-2 max-h-[300px] overflow-y-auto">
        {#each $segmentationModels as model}
          <button
            class="flex items-center gap-2 px-3 py-2 rounded-md border text-left transition-colors
            {selectedModel === model.name
              ? 'border-primary bg-primary/10 text-foreground'
              : 'border-border bg-muted/50 text-muted-foreground hover:bg-muted'}"
            on:click={() => handleSelect(model.name)}
          >
            <span class="text-sm flex-1">{model.name}</span>
            {#if model.provider_name}
              <span class="text-xs text-muted-foreground shrink-0">
                {model.provider_name.includes("@")
                  ? model.provider_name.substring(model.provider_name.indexOf("@") + 1)
                  : model.provider_name}
              </span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}

    {#if isVideo}
      <div class="h-px bg-border" />
      <div class="ml-4 flex flex-row items-center">
        <label for="positiveInteger" class="mr-2">Frames to track</label>
        <div
          class="flex w-20 h-10 items-center rounded-md border border-border bg-card pl-3 text-sm focus-within:ring-1 focus-within:ring-blue-500 focus-within:ring-offset-2"
        >
          <input
            class="w-full focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            type="number"
            id="positiveInteger"
            name="positiveInteger"
            min="0"
            step="1"
            value={$pixanoInferenceTrackingNbAdditionalFrames}
            on:change={(e) => {
              pixanoInferenceTrackingNbAdditionalFrames.set(parseInt(e.currentTarget.value));
            }}
          />
        </div>
      </div>
      <p class="w-60 ml-2 italic text-muted-foreground text-sm">
        First use of a tracking model may be long. A small value is advised first.
      </p>
      <div class="h-px bg-border" />
      <div class="ml-4 flex gap-4 items-center">
        <Checkbox
          handleClick={handleValTrackingClick}
          checked={$pixanoInferenceTracking.mustValidate}
        />
        <span>Validate before tracking</span>
      </div>
    {/if}

    <div class="h-px bg-border" />
    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton
        on:click={handleConfirm}
        disabled={!selectedModel && $segmentationModels.length > 0}
      >
        OK
      </PrimaryButton>
    </div>
  </div>
</div>
