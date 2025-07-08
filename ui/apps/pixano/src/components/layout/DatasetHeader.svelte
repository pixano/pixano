<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";

  import { ConfirmModal, IconButton, PrimaryButton } from "@pixano/core/src";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";

  import DatasetItemHeader from "./DatasetItemHeader.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { findNeighborItemId, getPageFromItemId } from "$lib/api/navigationApi";
  import { navItems } from "$lib/constants/headerConstants";
  import {
    currentDatasetStore,
    datasetItemIds,
    datasetTableStore,
    isLoadingNewItemStore,
    saveCurrentItemStore,
  } from "$lib/stores/datasetStores";

  export let pageId: string | null;

  let currentItemId: string;
  let isLoading: boolean;
  let canSaveCurrentItem: boolean;
  let showConfirmModal: string = "none";
  let newItemId: string = "none";

  const DATASET_ITEM_ROUTE = `/[dataset]/dataset/[itemId]`;

  const unsubscribeSaveCurrentItemStore = saveCurrentItemStore.subscribe(
    (value) => (canSaveCurrentItem = value.canSave),
  );

  const unsubscribeisLoadingNewItemStore = isLoadingNewItemStore.subscribe((value) => {
    isLoading = value;
  });

  $: unsubscribePage = page.subscribe((value) => {
    currentItemId = value.params.itemId;
  });

  onDestroy(() => {
    unsubscribeSaveCurrentItemStore();
    unsubscribeisLoadingNewItemStore();
    unsubscribePage();
  });

  const getDatasetItemDisplayCount = () => {
    const index = $datasetItemIds.indexOf(currentItemId);
    return `${index + 1} of ${$datasetItemIds.length}`;
  };

  // Handle bi-directional navigation using arrows
  const goToNeighborItem = async (direction: "previous" | "next") => {
    // Find the neighbor item id
    const neighborId = findNeighborItemId($datasetItemIds, direction, currentItemId);

    // If a neighbor item has been found
    if (neighborId) {
      const route = `/${$currentDatasetStore.id}/dataset/${neighborId}`;

      // Ask for confirmation if modifications have been made to the item
      if (canSaveCurrentItem) {
        newItemId = neighborId;
        return (showConfirmModal = route);
      }

      // Go to next/previous item
      currentItemId = neighborId;
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
      currentItemId = newItemId;
      newItemId = "none";
    }
    await goto(showConfirmModal);
    showConfirmModal = "none";
    saveCurrentItemStore.set({ canSave: false, shouldSave: false });
  };

  // Return to the previous page
  const handleReturnToPreviousPage = async () => {
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
    if (canSaveCurrentItem) {
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
      if (canSaveCurrentItem) {
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

<header
  class="w-full fixed z-40 font-Montserrat h-20 p-5 flex justify-between items-center shrink-0
      bg-white border-b border-slate-200 shadow-sm text-slate-800"
  use:preventUnsavedUnload
>
  {#if $page.route.id === DATASET_ITEM_ROUTE}
    <DatasetItemHeader
      {currentItemId}
      {isLoading}
      {handleSave}
      {goToNeighborItem}
      {handleReturnToPreviousPage}
      {navigateTo}
      {getDatasetItemDisplayCount}
    />
  {:else}
    {#if $currentDatasetStore}
      <div class="h-10 flex items-center font-semibold text-2xl">
        <div class="flex gap-4 items-center font-light">
          <div class="h-10 w-10">
            <IconButton on:click={() => navigateTo("/")} tooltipContent={"Back to Home"}>
              <img src={pixanoLogo} alt="Logo Pixano" class="w-8 h-8 mx-2" />
            </IconButton>
          </div>
          {$currentDatasetStore.name}
        </div>
      </div>
    {/if}
    <div class="flex gap-4">
      {#each navItems as { name, Icon }}
        <PrimaryButton
          isSelected={pageId?.includes(`/${name}`.toLowerCase())}
          on:click={() => navigateTo(`/${$currentDatasetStore.id}/${name.toLocaleLowerCase()}`)}
        >
          <Icon strokeWidth={1} />
          {name}
        </PrimaryButton>
      {/each}
    </div>
  {/if}
</header>
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
