<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowLeft, ArrowRight, ChevronLeft, Loader2Icon, Save } from "lucide-svelte";
  import { fade } from "svelte/transition";

  import { cn, IconButton, WorkspaceType } from "@pixano/core";
  import Toolbar from "@pixano/dataset-item-workspace/src/components/Toolbar.svelte";
  import { saveData } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

  import {
    currentDatasetStore,
    isLoadingNewItemStore,
  } from "$lib/stores/datasetStores";

  export let currentItemId: string;
  export let goToNeighborItem: (direction: "previous" | "next") => Promise<string | undefined>;
  export let handleReturnToPreviousPage: () => void;
  export let handleSave: () => void;
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
    if (event.shiftKey) {
      switch (event.code) {
        case "ArrowRight":
        case "KeyD":
          await goToNeighborItem("next");
          break;
        case "ArrowLeft":
        case "KeyA":
          await goToNeighborItem("previous");
          break;
      }
    }
    return event.key;
  };
</script>

{#if currentItemId}
  <div in:fade={{ duration: 200 }} class="flex-1 flex items-center justify-between h-full relative px-2">
    {#if $isLoadingNewItemStore}
      <div class="flex items-center gap-3 px-4">
        <Loader2Icon class="animate-spin text-primary h-4 w-4" />
        <span class="text-[11px] text-muted-foreground animate-pulse font-bold uppercase tracking-wider">Loading...</span>
      </div>
    {:else}
      <!-- LEFT: Navigation & Context -->
      <div class="flex items-center gap-3 min-w-[240px]">
        <button 
          on:click={handleReturnToPreviousPage}
          class="group flex items-center gap-2 px-2 py-1 rounded-xl hover:bg-primary/5 transition-all duration-200 border border-transparent hover:border-primary/10"
          title="Back to dataset"
        >
          <ChevronLeft class="h-4 w-4 text-primary opacity-0 -ml-1 group-hover:opacity-100 transition-all duration-300" />
          <span class="text-[13px] font-black uppercase tracking-tighter text-foreground/80 group-hover:text-primary transition-colors">
            {$currentDatasetStore?.name}
          </span>
        </button>

        <div class="h-4 w-px bg-border/40 mx-1"></div>

        <div class="flex items-center gap-1 bg-muted/20 rounded-xl border border-border/30 p-0.5 shadow-inner">
          <IconButton
            on:click={() => goToNeighborItem("previous")}
            tooltipContent="Previous (Shift + A)"
            class="h-7 w-7 hover:bg-background/80"
          >
            <ArrowLeft class="h-3.5 w-3.5" />
          </IconButton>
          
          <div class="flex items-baseline gap-1.5 px-2">
            <span class="text-[11px] font-black text-foreground/90 tabular-nums">
              {currentItemId}
            </span>
            <span class="text-[9px] text-muted-foreground font-bold opacity-40 uppercase tracking-tighter">
              {getDatasetItemDisplayCount()}
            </span>
          </div>

          <IconButton
            on:click={() => goToNeighborItem("next")}
            tooltipContent="Next (Shift + D)"
            class="h-7 w-7 hover:bg-background/80"
          >
            <ArrowRight class="h-3.5 w-3.5" />
          </IconButton>
        </div>
      </div>

      <!-- MIDDLE: Absolute Center Tools -->
      <div class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none">
        <div class="pointer-events-auto">
          {#if $currentDatasetStore}
            <Toolbar isVideo={$currentDatasetStore.workspace === WorkspaceType.VIDEO} />
          {/if}
        </div>
      </div>

      <!-- RIGHT: Action Group -->
      <div class="flex items-center justify-end min-w-[60px]">
        <IconButton
          disabled={$saveData.length === 0}
          on:click={handleSave}
          tooltipContent={$saveData.length > 0 ? `Save ${$saveData.length} changes` : "No changes to save"}
          class={cn(
            "h-10 w-10 transition-all duration-500 rounded-xl border",
            $saveData.length > 0 
              ? "bg-primary text-primary-foreground border-primary shadow-lg shadow-primary/20 scale-110 animate-pulse" 
              : "bg-background border-border text-muted-foreground opacity-40"
          )}
        >
          <Save class={cn("h-5 w-5 transition-transform duration-300", $saveData.length > 0 && "scale-110")} />
          {#if $saveData.length > 0}
            <span class="absolute -top-1 -right-1 flex h-4 w-4">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-foreground opacity-75"></span>
              <span class="relative inline-flex rounded-full h-4 w-4 bg-primary-foreground text-[9px] font-black text-primary items-center justify-center shadow-sm">
                {$saveData.length}
              </span>
            </span>
          {/if}
        </IconButton>
      </div>
    {/if}
  </div>
{/if}
<svelte:window on:keyup={onKeyUp} />
