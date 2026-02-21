<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";
  import { Loader2Icon, SaveIcon, ShieldAlertIcon, XIcon } from "lucide-svelte";
  import { cubicOut } from "svelte/easing";
  import { fade, fly } from "svelte/transition";
  import { untrack } from "svelte";

  import { Button } from "bits-ui";

  import { DatasetItem, effectProbe, type FeaturesValues, type SaveItem } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";
  import { buttonVariants } from "$lib/utils/buttonVariants";

  import Inspector from "./Inspector/InspectorInspector.svelte";
  import LoadModelModal from "./LoadModelModal.svelte";
  import { addOrUpdateSaveItem } from "$lib/utils/saveItemUtils";
  import {
    annotations,
    canSave,
    entities,
    itemMetas,
    modelsUiStore,
    newShape,
    resetWorkspaceStores,
    saveData,
    views,
  } from "$lib/stores/workspaceStores.svelte";
  import { videoControls } from "$lib/stores/videoStores.svelte";

  import { attachTrackletChildren, processDatasetItem } from "$lib/utils/itemDataProcessing";
  import { getTopEntityFromList } from "$lib/utils/entityLookupUtils";
  import { prepareSaveData } from "$lib/utils/saveDataProcessing";
  import { loadViewEmbeddings } from "$lib/utils/embeddingOperations";

  interface Props {
    featureValues: FeaturesValues;
    selectedItem: DatasetItem;
    handleSaveItem: (data: SaveItem[]) => Promise<void>;
    isLoading: boolean;
    shouldSaveCurrentItem: boolean;
    viewer: Snippet<[{ resize: number }]>;
  }

  let {
    featureValues,
    selectedItem,
    handleSaveItem,
    isLoading,
    shouldSaveCurrentItem,
    viewer,
  }: Props = $props();

  // Reset stores synchronously on mount to clear stale data from previous session
  resetWorkspaceStores();

  // Also reset on unmount to leave clean state
  $effect(() => {
    return () => {
      resetWorkspaceStores();
    };
  });

  // Utility vars for resizing with slide bar
  const defaultOIWidth = 450;
  let objectInspectorAreaMaxWidth = $state(defaultOIWidth);
  const minOIAreaWidth = 0;
  let initialOIAreaX = 0;
  let initialOIAreaWidth = 0;

  let isSaving: boolean = $state(false);
  let showAutogenBBoxAlert = $state(false);

  // --- Store probes via $effect (auto-cleanup, replaces subscribe + onDestroy) ---

  $effect(() => { effectProbe("Workspace.annotations", { size: annotations.value.length }); });
  $effect(() => { effectProbe("Workspace.entities", { size: entities.value.length }); });
  $effect(() => { effectProbe("Workspace.saveData", { size: saveData.value.length }); });
  $effect(() => { effectProbe("Workspace.newShape", { status: newShape.value?.status ?? "none" }); });

  // --- Data loading ---

  const loadData = () => {
    saveData.value = [];
    showAutogenBBoxAlert = false;
    views.value = selectedItem.views;

    const result = processDatasetItem(selectedItem, featureValues);

    if (result.videoSpeed !== undefined) {
      videoControls.update((old) => ({ ...old, videoSpeed: result.videoSpeed! }));
    }

    if (result.generatedBBoxes.length > 0) {
      showAutogenBBoxAlert = true;
      saveData.update((currentSd) => {
        let updated = currentSd;
        for (const item of result.generatedSaveItems) {
          updated = addOrUpdateSaveItem(updated, item);
        }
        return updated;
      });
    }

    // Set entities first so colorScale effect processes them before annotations
    entities.value = result.entities;

    // Attach tracklet children & top entities BEFORE writing to the store,
    // using the pure getTopEntityFromList to avoid reading entities through the proxy.
    // This collapses 2 annotation writes into 1.
    const withTracklets = attachTrackletChildren(
      result.annotations,
      (ann) => getTopEntityFromList(ann, result.entities),
    );
    annotations.value = withTracklets;

    itemMetas.value = {
      featuresList: featureValues || { main: {}, objects: {} },
      item: selectedItem.item,
      type: selectedItem.ui.type,
    };
  };

  // --- Item change detection ---

  let lastLoadedItemId: string | null = null;
  $effect(() => {
    const currentItemId = selectedItem?.item?.id;
    if (!currentItemId || currentItemId === lastLoadedItemId) return;
    lastLoadedItemId = currentItemId;
    untrack(() => {
      const currentShape = newShape.value;
      if (currentShape?.status !== "none") {
        newShape.value = { ...currentShape, status: "none" };
      }
      loadData();
    });
  });

  // --- View embeddings ---

  $effect(() => {
    modelsUiStore.value; // track changes
    if (selectedItem) loadViewEmbeddings();
  });

  // --- Save ---

  const onSave = async () => {
    isSaving = true;
    await handleSaveItem(prepareSaveData(saveData.value));
    saveData.value = [];
    isSaving = false;
  };

  $effect(() => {
    if (!shouldSaveCurrentItem) return;
    untrack(() => {
      if (!isSaving) {
        onSave().catch((err) => console.error(err));
      }
    });
  });

  // --- Resize ---

  const startExpand = (e: MouseEvent) => {
    initialOIAreaX = e.clientX;
    initialOIAreaWidth = objectInspectorAreaMaxWidth;
    window.addEventListener("mousemove", expand, true);
    window.addEventListener("mouseup", stopExpand, true);
  };

  const stopExpand = () => {
    window.removeEventListener("mousemove", expand, true);
    window.removeEventListener("mouseup", stopExpand, true);
  };

  const expand = (e: MouseEvent) => {
    const delta = e.clientX - initialOIAreaX;
    objectInspectorAreaMaxWidth = Math.max(minOIAreaWidth, initialOIAreaWidth - delta);
  };

  // --- Keyboard shortcut ---

  const handleKeyDown = (event: KeyboardEvent) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "s") {
      event.preventDefault();
      if (canSave.value && !isSaving) {
        void onSave();
      }
    }
  };
</script>

<svelte:window onkeydown={handleKeyDown} />

<div class="w-full h-full flex" role="tab" tabindex="0">
  {#if isSaving}
    <div
      class="h-full w-full flex justify-center items-center absolute top-0 left-0 bg-black/10 z-50"
    >
      <Loader2Icon class="animate-spin" />
    </div>
  {/if}
  <div
    class="flex flex-col w-full overflow-hidden"
    style={`max-width: calc(100%  - ${objectInspectorAreaMaxWidth}px);`}
  >
    {#if showAutogenBBoxAlert}
      <div
        class="bg-warning/10 border-b border-warning/20 px-4 py-2 flex items-center justify-between gap-4 animate-in slide-in-from-top duration-300"
        transition:fade
      >
        <div class="flex items-center gap-3">
          <div class="p-1.5 rounded-full bg-warning/20 text-warning">
            <ShieldAlertIcon size={18} />
          </div>
          <div class="flex flex-col">
            <span class="text-sm font-bold text-warning-foreground">
              Bounding boxes automatically generated
            </span>
            <span class="text-[11px] text-warning-foreground/60 leading-tight">
              Some masks were missing bounding boxes. They have been added for optimal visualization
              and thumbnails.
            </span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <Button.Root
            type="button"
            class={cn(buttonVariants({ variant: "outline" }), "h-8 px-3 border-warning/30 hover:bg-warning/20 text-warning-foreground gap-2 text-xs")}
            onclick={() => {
              void onSave();
              showAutogenBBoxAlert = false;
            }}
          >
            <SaveIcon size={14} />
            Save All
          </Button.Root>
          <button
            class="p-1.5 rounded-md hover:bg-card/10 text-warning-foreground/40 hover:text-warning-foreground transition-colors"
            onclick={() => (showAutogenBBoxAlert = false)}
            aria-label="Dismiss"
          >
            <XIcon size={16} />
          </button>
        </div>
      </div>
    {/if}
    <div
      id="datasetItemViewerDiv"
      class="flex-1 w-full overflow-hidden"
      in:fade={{ duration: 300, delay: 100 }}
    >
      <div class="h-full w-full max-w-full bg-canvas overflow-hidden">
        {#if isLoading}
          <div class="h-full w-full flex justify-center items-center">
            <Loader2Icon class="animate-spin text-white" />
          </div>
        {:else}
          {@render viewer({ resize: objectInspectorAreaMaxWidth + 1 })}
        {/if}
      </div>
    </div>
  </div>
  <button
    class="w-1.5 group relative bg-border hover:bg-primary/30 cursor-col-resize h-full transition-colors"
    onmousedown={startExpand}
    aria-label="Resize object inspector"
  >
    <div
      class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 rounded-full bg-border group-hover:bg-primary/50 transition-colors"
    ></div>
  </button>
  <div
    class="grow overflow-hidden bg-card"
    style={`width: ${objectInspectorAreaMaxWidth}px`}
    in:fly={{ x: 20, duration: 400, delay: 200, easing: cubicOut }}
  >
    <Inspector {isLoading} />
  </div>
  <LoadModelModal />
</div>
