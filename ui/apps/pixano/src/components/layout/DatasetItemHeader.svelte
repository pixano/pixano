<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowLeft, ArrowLeftCircleIcon, ArrowRight, Home, Loader2Icon } from "lucide-svelte";

  import { IconButton, ModelManager, PrimaryButton, WorkspaceType } from "@pixano/core";
  import Toolbar from "@pixano/dataset-item-workspace/src/components/Toolbar.svelte";

  import { currentDatasetStore } from "$lib/stores/datasetStores";

  export let currentItemId: string;
  export let isLoading: boolean;
  export let goToNeighborItem: (direction: "previous" | "next") => Promise<string | undefined>;
  export let handleReturnToPreviousPage: () => void;
  export let handleSave: () => void;
  export let navigateTo: (route: string) => Promise<string | undefined>;
  export let getDatasetItemDisplayCount: () => string;

  const onKeyUp = async (event: KeyboardEvent) => {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true" ||
      (event.target as Element)?.tagName === "INPUT"
    ) {
      // Ignore shortcut when typing text
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (event.shiftKey && event.key === "ArrowLeft") {
      await goToNeighborItem("previous");
    } else if (event.shiftKey && event.key === "ArrowRight") {
      await goToNeighborItem("next");
    }
    return event.key;
  };
</script>

{#if currentItemId}
  {#if isLoading}
    <Loader2Icon class="animate-spin" />
  {:else}
    <div class="flex items-center gap-4">
      <IconButton on:click={() => navigateTo("/")} tooltipContent={"Back to Home"}>
        <Home />
      </IconButton>
      <IconButton on:click={handleReturnToPreviousPage} tooltipContent={"Back to dataset"}>
        <ArrowLeftCircleIcon />
      </IconButton>
      {currentItemId}
      <IconButton
        on:click={() => goToNeighborItem("previous")}
        tooltipContent="Previous item (shift + left arrow)"
      >
        <ArrowLeft />
      </IconButton>
      <IconButton
        on:click={() => goToNeighborItem("next")}
        tooltipContent="Next item (shift + right arrow)"
      >
        <ArrowRight />
      </IconButton>
      <span>{getDatasetItemDisplayCount()}</span>
    </div>
    <Toolbar isVideo={$currentDatasetStore.workspace == WorkspaceType.VIDEO} />
    <ModelManager />
  {/if}
{/if}
<PrimaryButton on:click={handleSave}>Save</PrimaryButton>
<svelte:window on:keyup={onKeyUp} />
