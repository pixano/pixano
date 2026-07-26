<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { CaretLeft, CaretRight, CircleNotch, FloppyDisk } from "phosphor-svelte";
  import { fade } from "svelte/transition";

  import { Toolbar } from "../workspace";
  import { navigating } from "$app/state";
  import { currentDatasetStore } from "$lib/stores/appStores.svelte";
  import { saveData } from "$lib/stores/workspaceStores.svelte";
  import { cn, IconButton } from "$lib/ui";

  interface Props {
    currentItemId: string;
    goToNeighborItem: (direction: "previous" | "next") => Promise<void>;
    handleReturnToPreviousPage: () => void;
    handleReturnToLibrary?: () => void;
    handleSave: () => void;
    getWorkspaceRecordDisplayCount: () => string;
  }

  let {
    currentItemId,
    goToNeighborItem,
    handleReturnToPreviousPage,
    handleReturnToLibrary,
    handleSave,
    getWorkspaceRecordDisplayCount,
  }: Props = $props();

  const dirtyCount = $derived(saveData.value.length);

  const onKeyUp = async (event: KeyboardEvent) => {
    // Item navigation shortcuts should work globally, even when typing in a textarea
    if (event.shiftKey) {
      switch (event.code) {
        case "ArrowRight":
          await goToNeighborItem("next");
          return;
        case "ArrowLeft":
          await goToNeighborItem("previous");
          return;
      }
    }

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

    return event.key;
  };
</script>

{#if currentItemId}
  <div
    in:fade={{ duration: 200 }}
    class="grid h-full flex-1 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 px-2"
  >
    {#if navigating.from !== null}
      <div class="flex items-center gap-3 px-4">
        <CircleNotch weight="regular" class="h-4 w-4 animate-spin text-primary" />
        <span class="text-label">Loading…</span>
      </div>
      <div></div>
      <div></div>
    {:else}
      <!-- LEFT: breadcrumb — Library › dataset › record nav -->
      <nav class="flex min-w-0 items-center gap-2">
        {#if handleReturnToLibrary}
          <button
            type="button"
            onclick={handleReturnToLibrary}
            class="shrink-0 rounded-md px-1 text-sm font-medium text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Library
          </button>
          <CaretRight size={14} class="shrink-0 text-muted-foreground/50" />
        {/if}
        <button
          type="button"
          onclick={handleReturnToPreviousPage}
          title="Back to the dataset explorer"
          class="flex min-w-0 shrink items-center rounded-xl border border-primary/10 bg-primary/[0.03] px-3 py-1.5 transition-colors hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span class="truncate text-sm font-bold text-foreground">
            {currentDatasetStore.value?.name}
          </span>
        </button>
        <CaretRight size={14} class="shrink-0 text-muted-foreground/50" />
        <div class="flex min-w-0 items-center gap-1">
          <IconButton
            onclick={() => goToNeighborItem("previous")}
            tooltipContent="Previous record (Shift + ←)"
            class="h-7 w-7 rounded-lg"
          >
            <CaretLeft class="h-3.5 w-3.5" />
          </IconButton>
          <span
            class="max-w-[180px] truncate font-mono text-xs text-muted-foreground"
            title={currentItemId}
          >
            {currentItemId}
          </span>
          <span
            class="inline-flex h-7 shrink-0 items-center whitespace-nowrap rounded-full border border-border/40 bg-muted/40 px-2.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground tabular-nums"
          >
            {getWorkspaceRecordDisplayCount()}
          </span>
          <IconButton
            onclick={() => goToNeighborItem("next")}
            tooltipContent="Next record (Shift + →)"
            class="h-7 w-7 rounded-lg"
          >
            <CaretRight class="h-3.5 w-3.5" />
          </IconButton>
        </div>
      </nav>

      <!-- CENTER: annotation tools (in flow — no absolute overlap) -->
      <div class="flex items-center justify-center">
        {#if currentDatasetStore.value}
          <Toolbar />
        {/if}
      </div>

      <!-- RIGHT: save -->
      <div class="flex items-center justify-end">
        <button
          type="button"
          disabled={dirtyCount === 0}
          onclick={handleSave}
          title={dirtyCount > 0
            ? `Save ${dirtyCount} change${dirtyCount > 1 ? "s" : ""} (Ctrl/⌘ + S)`
            : "No changes to save"}
          class={cn(
            "inline-flex h-10 items-center gap-2 rounded-xl px-4 text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            dirtyCount > 0
              ? "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
              : "cursor-default border border-border bg-transparent text-muted-foreground opacity-60",
          )}
        >
          <FloppyDisk size={16} />
          Save
          {#if dirtyCount > 0}
            <span
              class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary-foreground/20 px-1.5 text-[10px] tabular-nums"
            >
              {dirtyCount}
            </span>
          {/if}
        </button>
      </div>
    {/if}
  </div>
{/if}
<svelte:window onkeyup={onKeyUp} />
