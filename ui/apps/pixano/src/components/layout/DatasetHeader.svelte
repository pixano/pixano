<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { fade } from "svelte/transition";

  import { ConfirmModal, PrimaryButton } from "@pixano/core";

  import DatasetItemHeader from "./DatasetItemHeader.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { findNeighborItemId, getPageFromItemId } from "$lib/api/navigationApi";
  import { navItems } from "$lib/constants/headerConstants";
  import {
    currentDatasetStore,
    datasetItemIds,
    datasetTableStore,
    saveCurrentItemStore,
  } from "$lib/stores/datasetStores";

  export let pageId: string | null;

  let showConfirmModal: string = "none";
  let newItemId: string = "none";

  const DATASET_ITEM_ROUTE = `/[dataset]/dataset/[itemId]`;

  $: currentItemId = $page.params.itemId;

  const getDatasetItemDisplayCount = () => {
    const index = $datasetItemIds.indexOf(currentItemId);
    if (index === -1) return "0 of 0";
    return `${index + 1} of ${$datasetItemIds.length}`;
  };

  // Handle bi-directional navigation using arrows
  const goToNeighborItem = async (direction: "previous" | "next") => {
    if (!$currentDatasetStore) return;

    // Find the neighbor item id
    const neighborId = findNeighborItemId($datasetItemIds, direction, currentItemId);

    // If a neighbor item has been found
    if (neighborId) {
      const route = `/${$currentDatasetStore.id}/dataset/${neighborId}`;

      // Ask for confirmation if modifications have been made to the item
      if ($saveCurrentItemStore.canSave) {
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
    saveCurrentItemStore.set({ canSave: false, shouldSave: false });
  };

  // Return to the previous page
  const handleReturnToPreviousPage = async () => {
    if (!$currentDatasetStore) return;
    if (currentItemId) {
      // Update the current page to ensure that we follow the selected item
      datasetTableStore.update((pagination) => {
        pagination.currentPage = getPageFromItemId($datasetItemIds, currentItemId);
        return pagination;
      });
      await navigateTo(`/${$currentDatasetStore.id}/dataset`);
    } else await navigateTo("/");
  };

  const navigateTo = async (route: string) => {
    if ($saveCurrentItemStore.canSave) {
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
      if ($saveCurrentItemStore.canSave) {
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
  {#if $page.route.id === DATASET_ITEM_ROUTE}
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
        {#if $currentDatasetStore}
          <div
            class="flex items-center px-4 py-1.5 bg-primary/[0.03] border border-primary/10 rounded-xl max-w-[300px]"
          >
            <span class="text-sm font-bold text-foreground truncate">
              {$currentDatasetStore.name}
            </span>
          </div>
        {/if}

        <div class="flex items-center gap-2">
          {#each navItems as { name, Icon }}
            <PrimaryButton
              isSelected={pageId?.includes(`/${name}`.toLowerCase())}
              on:click={() => navigateTo(`/${$currentDatasetStore.id}/${name.toLocaleLowerCase()}`)}
              class="h-9 px-4 text-xs font-bold uppercase tracking-wider"
            >
              <Icon class="h-3.5 w-3.5" />
              {name}
            </PrimaryButton>
          {/each}
        </div>
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
    on:confirm={handleSaveAndContinue}
    on:alternative={handleContinue}
    on:cancel={() => (showConfirmModal = "none")}
  />
{/if}
