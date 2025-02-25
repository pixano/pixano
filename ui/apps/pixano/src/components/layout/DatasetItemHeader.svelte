<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowLeft, ArrowLeftCircleIcon, ArrowRight, Home, Loader2Icon } from "lucide-svelte";

  import { IconButton, PrimaryButton, WorkspaceType } from "@pixano/core/src";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
  import Toolbar from "@pixano/dataset-item-workspace/src/components/Toolbar.svelte";

  import { currentDatasetStore } from "$lib/stores/datasetStores";

  export let currentItemId: string;
  export let isLoading: boolean;
  export let goToNeighborItem: (direction: "previous" | "next") => Promise<string | undefined>;
  export let handleReturnToPreviousPage: () => void;
  export let handleSave: () => void;
  export let navigateTo: (route: string) => Promise<string | undefined>;

  const onKeyUp = async (event: KeyboardEvent) => {
    if ((event.target as Element)?.tagName === "INPUT") return event.preventDefault();
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
    </div>
    <Toolbar isVideo={$currentDatasetStore.workspace == WorkspaceType.VIDEO} />
  {/if}
{/if}
<PrimaryButton on:click={handleSave}>Save</PrimaryButton>
<svelte:window on:keyup={onKeyUp} />
