<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleNotch } from "phosphor-svelte";
  import type { Snippet } from "svelte";
  import { untrack } from "svelte";
  import { cubicOut } from "svelte/easing";
  import { fade, fly } from "svelte/transition";

  import WorkspaceInspectorPanel from "./Inspector/WorkspaceInspectorPanel.svelte";
  import LoadModelModal from "./LoadModelModal.svelte";
  import { playbackState } from "$lib/stores/videoStores.svelte";
  import {
    annotations,
    canSave,
    entities,
    generatedPreviewBBoxes,
    itemMetas,
    modelsUiStore,
    newShape,
    resetWorkspaceStores,
    saveData,
    views,
  } from "$lib/stores/workspaceStores.svelte";
  import {
    DatasetItem,
    effectProbe,
    type FeaturesValues,
    type SaveItem,
  } from "$lib/ui";
  import { loadViewEmbeddings } from "$lib/utils/embeddingOperations";
  import { getTopEntityFromList } from "$lib/utils/entityLookupUtils";
  import { attachTrackChildren, processDatasetItem } from "$lib/utils/itemDataProcessing";
  import { prepareSaveData } from "$lib/utils/saveItemUtils";

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

  // --- Store probes via $effect (auto-cleanup, replaces subscribe + onDestroy) ---

  $effect(() => {
    effectProbe("Workspace.annotations", { size: annotations.value.length });
  });
  $effect(() => {
    effectProbe("Workspace.entities", { size: entities.value.length });
  });
  $effect(() => {
    effectProbe("Workspace.saveData", { size: saveData.value.length });
  });
  $effect(() => {
    effectProbe("Workspace.newShape", { status: newShape.value?.status ?? "none" });
  });

  // --- Data loading ---

  const loadData = () => {
    saveData.value = [];
    generatedPreviewBBoxes.value = [];
    views.value = selectedItem.views;

    const result = processDatasetItem(selectedItem, featureValues);

    if (result.videoSpeed !== undefined) {
      playbackState.update((old) => ({ ...old, videoSpeed: result.videoSpeed }));
    }

    // Set entities first so colorScale effect processes them before annotations
    entities.value = result.entities;
    generatedPreviewBBoxes.value = result.previewBBoxes;

    // Attach track children & top entities BEFORE writing to the store,
    // using the pure getTopEntityFromList to avoid reading entities through the proxy.
    // This collapses 2 annotation writes into 1.
    const withTracks = attachTrackChildren(result.annotations, (ann) =>
      getTopEntityFromList(ann, result.entities),
    );
    annotations.value = withTracks;

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
    void modelsUiStore.value; // track changes
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
      <CircleNotch weight="regular" class="animate-spin" />
    </div>
  {/if}
  <div
    class="flex flex-col w-full overflow-hidden"
    style={`max-width: calc(100%  - ${objectInspectorAreaMaxWidth}px);`}
  >
    <div
      id="datasetItemViewerDiv"
      class="flex-1 w-full overflow-hidden"
      in:fade={{ duration: 300, delay: 100 }}
    >
      <div class="h-full w-full max-w-full bg-canvas overflow-hidden">
        {@render viewer({ resize: objectInspectorAreaMaxWidth + 1 })}
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
    <WorkspaceInspectorPanel {isLoading} />
  </div>
  <LoadModelModal />
</div>
