<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowLeft, ArrowRight, Home, Loader2Icon } from "lucide-svelte";

  import { IconButton, PrimaryButton } from "@pixano/core/src";
  import Toolbar from "@pixano/dataset-item-workspace/src/components/Toolbar.svelte";

  export let currentItemId: string;
  export let isLoading: boolean;
  export let goToNeighborItem: (direction: "previous" | "next") => Promise<string | undefined>;
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
      <IconButton on:click={() => navigateTo("/")}><Home /></IconButton>
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

    <Toolbar />
    <!-- <Toolbar isVideo={selectedItem.ui.type === WorkspaceType.VIDEO} /> -->
  {/if}
{/if}
<PrimaryButton on:click={handleSave}>Save</PrimaryButton>
<svelte:window on:keyup={onKeyUp} />
