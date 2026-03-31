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
  import type { ResourceMutation } from "$lib/api/resourcePayloads";
  import { currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import { playbackState } from "$lib/stores/videoStores.svelte";
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
  import type { WorkspaceData } from "$lib/types/workspace";
  import { effectProbe, type FeaturesValues } from "$lib/ui";
  import { loadViewEmbeddings } from "$lib/utils/embeddingOperations";
  import { buildWorkspaceRuntimeData } from "$lib/utils/itemDataProcessing";
  import { setWorkspaceContext } from "$lib/workspace/context";
  import type { WorkspaceManifest } from "$lib/workspace/manifest";

  interface Props {
    featureValues: FeaturesValues;
    workspaceManifest: WorkspaceManifest;
    workspaceData: WorkspaceData;
    handleSaveItem: (data: ResourceMutation[]) => Promise<void>;
    isLoading: boolean;
    viewer: Snippet<[{ resize: number }]>;
  }

  let {
    featureValues,
    workspaceManifest,
    workspaceData,
    handleSaveItem,
    isLoading,
    viewer,
  }: Props = $props();

  setWorkspaceContext({
    get manifest() {
      return workspaceManifest;
    },
    get featureValues() {
      return featureValues;
    },
  });

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
  let lastHandledSaveRequestId = $state<number | null>(null);

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
    views.value = workspaceData.views;

    const result = buildWorkspaceRuntimeData(workspaceData, featureValues);

    if (result.videoSpeed !== undefined) {
      playbackState.update((old) => ({ ...old, videoSpeed: result.videoSpeed }));
    }

    // Set entities first so colorScale effect processes them before annotations
    entities.value = result.entities;

    annotations.value = result.annotations;

    itemMetas.value = {
      featuresList: featureValues || { main: {}, objects: {} },
      item: workspaceData.item,
      type: workspaceData.ui.type,
    };
  };

  // --- Item change detection ---

  let lastLoadedItemId: string | null = null;
  $effect(() => {
    const currentItemId = workspaceData?.item?.id;
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
    if (workspaceData) loadViewEmbeddings();
  });

  // --- Save ---

  const onSave = async (requestId: number | null) => {
    isSaving = true;
    try {
      await handleSaveItem(saveData.value);
      saveData.value = [];
      if (requestId !== null) {
        currentItemSaveCoordinator.setSaveSucceeded(requestId);
      }
    } catch (error) {
      if (requestId !== null) {
        currentItemSaveCoordinator.setSaveFailed(undefined, requestId);
      }
      console.error(error);
    } finally {
      isSaving = false;
    }
  };

  $effect(() => {
    const activeRequestId = currentItemSaveCoordinator.value.activeRequestId;
    const saveStatus = currentItemSaveCoordinator.value.status;
    if (saveStatus !== "saving" || activeRequestId === null) return;
    if (activeRequestId === lastHandledSaveRequestId) return;
    untrack(() => {
      if (!isSaving) {
        lastHandledSaveRequestId = activeRequestId;
        void onSave(activeRequestId);
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
        void currentItemSaveCoordinator.requestSave();
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
