<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Tooltip } from "bits-ui";
  import {
    ArrowLeft,
    CaretLeft,
    CaretRight,
    Check,
    CircleNotch,
    FloppyDisk,
  } from "phosphor-svelte";
  import { fade } from "svelte/transition";

  import { Toolbar } from "../workspace";
  import { navigating } from "$app/state";
  import { currentDatasetStore } from "$lib/stores/appStores.svelte";
  import { saveData } from "$lib/stores/workspaceStores.svelte";
  import { IconButton } from "$lib/ui";

  interface Props {
    currentItemId: string;
    goToNeighborItem: (direction: "previous" | "next") => Promise<void>;
    handleReturnToPreviousPage: () => void;
    handleSave: () => void;
    getRecordPosition: () => { position: number | null; total: number | null };
  }

  let {
    currentItemId,
    goToNeighborItem,
    handleReturnToPreviousPage,
    handleSave,
    getRecordPosition,
  }: Props = $props();

  const dirtyCount = $derived(saveData.value.length);
  const recordPosition = $derived(getRecordPosition());

  const recordLabel = $derived.by(() => {
    const { position, total } = recordPosition;
    return position != null && total != null ? `${position} / ${total}` : "— / —";
  });

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
      <div class="flex items-center gap-2 px-1">
        <CircleNotch weight="regular" class="h-4 w-4 animate-spin text-primary" />
        <span class="text-sm text-muted-foreground">Loading…</span>
      </div>
      <div></div>
      <div></div>
    {:else}
      <!-- LEFT: back to explorer · dataset name · record position -->
      <nav class="flex min-w-0 items-center gap-2">
        <IconButton
          onclick={handleReturnToPreviousPage}
          tooltipContent="Back to explorer"
          class="h-8 w-8 shrink-0 rounded-lg"
        >
          <ArrowLeft class="h-4 w-4" />
        </IconButton>
        <Tooltip.Root>
          <Tooltip.Trigger
            type="button"
            onclick={handleReturnToPreviousPage}
            class="min-w-0 shrink truncate rounded-md px-1 text-sm font-semibold text-foreground transition-colors hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {currentDatasetStore.value?.name}
          </Tooltip.Trigger>
          <Tooltip.Content
            side="bottom"
            sideOffset={6}
            class="z-[9999] overflow-hidden rounded-md border border-border/40 bg-popover/95 backdrop-blur-md px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm"
          >
            <p>Back to explorer</p>
          </Tooltip.Content>
        </Tooltip.Root>
        <span class="shrink-0 text-sm text-muted-foreground/50">·</span>
        <div class="flex shrink-0 items-center gap-1">
          <IconButton
            onclick={() => goToNeighborItem("previous")}
            disabled={recordPosition.position === null}
            tooltipContent="Previous record (Shift + ←)"
            class="h-7 w-7 rounded-lg"
          >
            <CaretLeft class="h-3.5 w-3.5" />
          </IconButton>
          <Tooltip.Root>
            <Tooltip.Trigger>
              {#snippet child({ props })}
                <span {...props} class="text-sm tabular-nums text-muted-foreground">
                  {recordLabel}
                </span>
              {/snippet}
            </Tooltip.Trigger>
            <Tooltip.Content
              side="bottom"
              sideOffset={6}
              class="z-[9999] overflow-hidden rounded-md border border-border/40 bg-popover/95 backdrop-blur-md px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm"
            >
              <p>Record ID: {currentItemId}</p>
            </Tooltip.Content>
          </Tooltip.Root>
          <IconButton
            onclick={() => goToNeighborItem("next")}
            disabled={recordPosition.position === null}
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
        {#if dirtyCount > 0}
          <Tooltip.Root>
            <Tooltip.Trigger
              type="button"
              onclick={handleSave}
              class="inline-flex h-9 items-center gap-2 rounded-xl bg-primary px-3.5 text-xs font-bold uppercase tracking-wider text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <FloppyDisk size={14} />
              Save
              <span
                class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary-foreground/20 px-1.5 text-[10px] tabular-nums"
              >
                {dirtyCount}
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content
              side="bottom"
              sideOffset={6}
              class="z-[9999] overflow-hidden rounded-md border border-border/40 bg-popover/95 backdrop-blur-md px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm"
            >
              <p>Save {dirtyCount} change{dirtyCount > 1 ? "s" : ""} (Ctrl/⌘ + S)</p>
            </Tooltip.Content>
          </Tooltip.Root>
        {:else}
          <Tooltip.Root>
            <Tooltip.Trigger>
              {#snippet child({ props })}
                <span
                  {...props}
                  role="status"
                  class="inline-flex h-9 items-center gap-1.5 px-3.5 text-xs font-medium text-muted-foreground"
                >
                  <Check size={14} />
                  Saved
                </span>
              {/snippet}
            </Tooltip.Trigger>
            <Tooltip.Content
              side="bottom"
              sideOffset={6}
              class="z-[9999] overflow-hidden rounded-md border border-border/40 bg-popover/95 backdrop-blur-md px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm"
            >
              <p>No changes to save</p>
            </Tooltip.Content>
          </Tooltip.Root>
        {/if}
      </div>
    {/if}
  </div>
{/if}
<svelte:window onkeyup={onKeyUp} />
