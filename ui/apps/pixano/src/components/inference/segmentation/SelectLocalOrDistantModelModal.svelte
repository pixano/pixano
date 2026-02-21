<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Server, Wand2Icon } from "lucide-svelte";

  import {
    Checkbox,
    PrimaryButton,
    WorkspaceType,
  } from "$lib/ui";

  import {
    inferenceServerStore,
    segmentationModels,
    selectedSegmentationModelName,
  } from "$lib/stores/inferenceStores.svelte";
  import {
    pixanoInferenceTracking,
    pixanoInferenceTrackingNbAdditionalFrames,
  } from "$lib/stores/inferenceStores.svelte";
  import { itemMetas } from "$lib/stores/workspaceStores.svelte";

  interface Props {
    onConfirm?: () => void;
    onCancel?: () => void;
  }

  let { onConfirm, onCancel }: Props = $props();

  const isVideo = $derived(itemMetas.value?.type === WorkspaceType.VIDEO);

  let selectedModel = $state("");
  $effect(() => {
    const availableModels = segmentationModels.value;
    const hasCurrentSelection = availableModels.some((model) => model.name === selectedModel);
    if (hasCurrentSelection) return;
    selectedModel = selectedSegmentationModelName.value ?? (availableModels[0]?.name ?? "");
  });

  const handleSelect = (modelName: string) => {
    selectedModel = modelName;
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
    selectedSegmentationModelName.value = selectedModel || null;
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
      <Wand2Icon size={18} class="text-primary" />
    </div>
    <p class="font-bold text-sm tracking-tight">Smart Segmentation Model</p>
  </div>

  <div class="flex flex-col p-6 gap-6">
    {#if !inferenceServerStore.value.connected}
      <div class="flex flex-col items-center gap-4 py-4 text-center">
        <div class="p-3 rounded-full bg-muted/50">
          <Server size={24} class="text-muted-foreground/50" />
        </div>
        <p class="text-xs text-muted-foreground leading-relaxed px-4">
          Connect to an inference server from the toolbar to use AI models.
        </p>
      </div>
    {:else if segmentationModels.value.length === 0}
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
          {#each segmentationModels.value as model}
            <button
              class="flex flex-col gap-1 px-4 py-3 rounded-xl border text-left transition-all duration-200
              {selectedModel === model.name
                ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                : 'border-border/60 bg-muted/20 hover:border-border hover:bg-muted/40'}"
              onclick={() => handleSelect(model.name)}
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
          <Checkbox
            handleClick={handleValTrackingClick}
            checked={pixanoInferenceTracking.value.mustValidate}
          />
          <span class="text-xs font-medium text-foreground/80">Validate before tracking</span>
        </div>
      </div>
    {/if}

    <div class="flex flex-row gap-3 pt-2">
      <PrimaryButton onclick={handleCancel} class="flex-1 h-10">Cancel</PrimaryButton>
      <PrimaryButton
        onclick={handleConfirm}
        isSelected
        disabled={!selectedModel && segmentationModels.value.length > 0}
        class="flex-1 h-10"
      >
        Confirm
      </PrimaryButton>
    </div>
  </div>
</div>
