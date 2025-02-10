<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { Loader2Icon } from "lucide-svelte";

  import pixanoLogo from "@pixano/core/src/assets/pixano.png";

  import { ConfirmModal, PrimaryButton } from "@pixano/core/src";

  import { findNeighborItemId } from "$lib/api/navigationApi";
  import {
    currentDatasetStore,
    isLoadingNewItemStore,
    saveCurrentItemStore,
  } from "$lib/stores/datasetStores";
  import Toolbar from "@pixano/dataset-item-workspace/src/components/Toolbar/Toolbar.svelte";

  export let pageId: string | null;
  export let datasetItemsIds: string[];

  let currentItemId: string;
  let isLoading: boolean;
  let canSaveCurrentItem: boolean;
  let showConfirmModal: string = "none";
  let newItemId: string = "none";

  saveCurrentItemStore.subscribe((value) => (canSaveCurrentItem = value.canSave));

  isLoadingNewItemStore.subscribe((value) => {
    isLoading = value;
  });

  $: page.subscribe((value) => {
    currentItemId = value.params.itemId;
  });

  // Handle bi-directional navigation using arrows
  const goToNeighborItem = async (direction: "previous" | "next") => {
    // Find the neighbor item id
    const neighborId = findNeighborItemId(datasetItemsIds, direction, currentItemId);

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

  const onKeyUp = async (event: KeyboardEvent) => {
    if ((event.target as Element)?.tagName === "INPUT") return event.preventDefault();
    if (event.shiftKey && event.key === "ArrowLeft") {
      await goToNeighborItem("previous");
    } else if (event.shiftKey && event.key === "ArrowRight") {
      await goToNeighborItem("next");
    }
    return event.key;
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
  const preventUnsavedUnload = (_: HTMLElement) => {
    const checkNavigation = (e: BeforeUnloadEvent) => {
      if (canSaveCurrentItem) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", checkNavigation);
    return {
      destroy() {
        window.removeEventListener("beforeunload", checkNavigation);
      },
    };
  };
</script>

<header
  class="w-full h-16 p-5 font-Montserrat flex justify-between items-center shrink-0 bg-white border-b border-slate-200 shadow-sm text-slate-800"
  use:preventUnsavedUnload
>
  <div class="flex items-center gap-4">
    <button on:click={() => navigateTo("/")} class="h-10 w-10">
      <img src={pixanoLogo} alt="Logo Pixano" class="w-8 h-8 mx-2" />
    </button>
    {#if isLoading}
      <Loader2Icon class="animate-spin" />
    {:else if currentItemId}
      {currentItemId}
    {/if}
  </div>
  <Toolbar />
  <PrimaryButton isSelected={true} on:click={handleSave}>Save</PrimaryButton>
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
<svelte:window on:keyup={onKeyUp} />
