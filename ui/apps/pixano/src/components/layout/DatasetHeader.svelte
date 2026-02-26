<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { fade } from "svelte/transition";

  import { ConfirmModal, PrimaryButton } from "$lib/ui";

  import DatasetItemHeader from "./DatasetItemHeader.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import {
    EXPLORER_ROUTE_ID,
    WORKSPACE_ROUTE_ID,
    findNeighborItemId,
    getPageFromItemId,
    getExplorerRoute,
    getWorkspaceRoute,
  } from "$lib/utils/routes";
  import {
    currentDatasetStore,
    datasetItemIds,
    saveCurrentItemStore,
  } from "$lib/stores/appStores.svelte";

  interface Props {
    pageId: string | null;
  }

  let { pageId }: Props = $props();

  let showConfirmModal: string = $state("none");
  let newItemId: string = "none";

  let currentItemId = $derived(page.params.itemId);
  const isWorkspaceRoute = $derived(page.route.id === WORKSPACE_ROUTE_ID);

  const getDatasetItemDisplayCount = () => {
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
      if (saveCurrentItemStore.value.canSave) {
        newItemId = neighborId;
        return (showConfirmModal = route);
      }

      // Go to next/previous item
      await goto(route);
    }
  };

  const handleSave = () => {
    saveCurrentItemStore.update((old) => ({ ...old, shouldSave: true }));
  };

  const handleSaveAndContinue = async () => {
    handleSave();
    await handleContinue();
  };

  const handleContinue = async () => {
    if (newItemId !== "none") {
      newItemId = "none";
    }
    await goto(showConfirmModal);
    showConfirmModal = "none";
    saveCurrentItemStore.value = { canSave: false, shouldSave: false };
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
    if (saveCurrentItemStore.value.canSave) {
      return (showConfirmModal = route);
    }
    await goto(route);
  };

  //Note: the two following function aims to prevent losing unsaved changes after BROWSER actions
  //(pixano site internal navigation is already covered)
  //first one on browser refresh (for this one, we can't (?) customize the message)
  //second one on browser navigation (back/forward)
  // parameter is given, but we don't need it -- if we don't take it, tslint warns...
  // eslint-disable-next-line
  function preventUnsavedUnload(_: HTMLElement) {
    function checkNavigation(e: BeforeUnloadEvent) {
      if (saveCurrentItemStore.value.canSave) {
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
    <DatasetItemHeader
      {currentItemId}
      {handleSave}
      {goToNeighborItem}
      {handleReturnToPreviousPage}
      {getDatasetItemDisplayCount}
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
{#if showConfirmModal !== "none"}
  <ConfirmModal
    message="You have unsaved changes"
    confirm="Save and continue"
    alternativeAction="Continue without saving"
    onConfirm={handleSaveAndContinue}
    onAlternative={handleContinue}
    onCancel={() => (showConfirmModal = "none")}
  />
{/if}
