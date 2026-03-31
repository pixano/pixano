<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { fade } from "svelte/transition";

  import WorkspaceRecordHeader from "./WorkspaceRecordHeader.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import {
    currentDatasetStore,
    currentItemSaveCoordinator,
    datasetItemIds,
  } from "$lib/stores/appStores.svelte";
  import { PrimaryButton, UnsavedChangesDialog } from "$lib/ui";
  import {
    EXPLORER_ROUTE_ID,
    findNeighborItemId,
    getExplorerRoute,
    getPageFromItemId,
    getWorkspaceRoute,
    WORKSPACE_ROUTE_ID,
  } from "$lib/utils/routes";

  interface Props {
    pageId: string | null;
  }

  let { pageId }: Props = $props();

  let pendingNavigationRoute = $state<string | null>(null);
  let isDestroyed = false;

  let currentItemId = $derived(page.params.itemId);
  const isWorkspaceRoute = $derived(page.route.id === WORKSPACE_ROUTE_ID);
  const saveState = $derived(currentItemSaveCoordinator.value);

  $effect(() => {
    return () => {
      isDestroyed = true;
    };
  });

  $effect(() => {
    if (page.route.id === WORKSPACE_ROUTE_ID) return;
    currentItemSaveCoordinator.resetForItemChange();
  });

  const getWorkspaceRecordDisplayCount = () => {
    const index = datasetItemIds.value.indexOf(currentItemId);
    if (index === -1) return "0 of 0";
    return `${index + 1} of ${datasetItemIds.value.length}`;
  };

  // Handle bi-directional navigation using arrows
  const goToNeighborItem = async (direction: "previous" | "next") => {
    if (!currentDatasetStore.value) return;

    // Find the neighbor item id
    const neighborId = findNeighborItemId(datasetItemIds.value, direction, currentItemId);

    // If a neighbor item has been found
    if (neighborId) {
      const route = getWorkspaceRoute(currentDatasetStore.value.id, neighborId);

      // Ask for confirmation if modifications have been made to the item
      if (saveState.isDirty) {
        pendingNavigationRoute = route;
        return;
      }

      // Go to next/previous item
      await goto(route);
    }
  };

  const handleSave = () => {
    void currentItemSaveCoordinator.requestSave();
  };

  const handleSaveAndContinue = async () => {
    const route = pendingNavigationRoute;
    if (!route) return;

    const result = await currentItemSaveCoordinator.requestSave();
    if (!result.ok) return;

    pendingNavigationRoute = null;
    await goto(route);
  };

  const handleDiscardAndContinue = async () => {
    const route = pendingNavigationRoute;
    if (!route) return;

    pendingNavigationRoute = null;
    currentItemSaveCoordinator.beginDiscardBypass();

    try {
      await goto(route);
    } finally {
      if (!isDestroyed) {
        currentItemSaveCoordinator.endDiscardBypass();
      }
    }
  };

  // Return to the previous page
  const handleReturnToPreviousPage = async () => {
    if (!currentDatasetStore.value) return;
    if (currentItemId) {
      const targetPage = getPageFromItemId(datasetItemIds.value, currentItemId);
      await navigateTo(getExplorerRoute(currentDatasetStore.value.id, `page=${targetPage}`));
    } else await navigateTo("/");
  };

  const navigateTo = async (route: string) => {
    if (saveState.isDirty) {
      pendingNavigationRoute = route;
      return;
    }
    await goto(route);
  };

  // Prevent losing unsaved changes on browser-level unloads.
  // Internal app navigation is handled by the dialog flow above.
  // The parameter is unused but required by the Svelte action signature.
  // eslint-disable-next-line
  function preventUnsavedUnload(_: HTMLElement) {
    function checkNavigation(e: BeforeUnloadEvent) {
      if (
        currentItemSaveCoordinator.value.isDirty &&
        currentItemSaveCoordinator.value.guardMode === "armed"
      ) {
        e.preventDefault();
      }
    }
    window.addEventListener("beforeunload", checkNavigation);
    return {
      destroy() {
        window.removeEventListener("beforeunload", checkNavigation);
      },
    };
  }
</script>

<div class="h-full w-full flex items-center" use:preventUnsavedUnload>
  {#if isWorkspaceRoute}
    <WorkspaceRecordHeader
      {currentItemId}
      {handleSave}
      {goToNeighborItem}
      {handleReturnToPreviousPage}
      {getWorkspaceRecordDisplayCount}
    />
  {:else}
    <div in:fade={{ duration: 200 }} class="flex-1 flex items-center justify-between h-full">
      <div class="flex items-center gap-6">
        {#if currentDatasetStore.value}
          <div
            class="flex items-center px-4 py-1.5 bg-primary/[0.03] border border-primary/10 rounded-xl max-w-[300px]"
          >
            <span class="text-sm font-bold text-foreground truncate">
              {currentDatasetStore.value.name}
            </span>
          </div>
        {/if}

        <PrimaryButton
          isSelected={pageId === EXPLORER_ROUTE_ID}
          onclick={() => navigateTo(getExplorerRoute(currentDatasetStore.value.id))}
          class="h-9 px-4 text-xs font-bold uppercase tracking-wider"
        >
          Dataset
        </PrimaryButton>
      </div>

      <!-- Placeholder for Right zone in browser view to maintain symmetry -->
      <div class="w-10"></div>
    </div>
  {/if}
</div>
{#if pendingNavigationRoute !== null}
  <UnsavedChangesDialog
    isSaving={saveState.status === "saving"}
    errorMessage={saveState.status === "failed" ? saveState.errorMessage : null}
    onSave={handleSaveAndContinue}
    onDiscard={handleDiscardAndContinue}
    onCancel={() => (pendingNavigationRoute = null)}
  />
{/if}
