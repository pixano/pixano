<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CaretDoubleLeft, CaretDoubleRight, CaretLeft, CaretRight } from "phosphor-svelte";

  import type { DatasetBrowser } from "$lib/ui";
  import { Select } from "$lib/ui";

  interface Props {
    selectedDataset: DatasetBrowser;
    currentPage: number;
    pageSize: number;
    /** Page-size choices; pass an empty list to hide the selector (e.g. ranked mode). */
    pageSizeOptions?: number[];
    onPageChange: (page: number) => void;
    onPageSizeChange?: (size: number) => void;
  }

  let {
    selectedDataset,
    currentPage,
    pageSize,
    pageSizeOptions = [20, 50, 100],
    onPageChange,
    onPageSizeChange,
  }: Props = $props();

  const total = $derived(selectedDataset.pagination.total_size);
  const pageCount = $derived(Math.max(Math.ceil((total || 1) / Math.max(pageSize, 1)), 1));
  const rangeStart = $derived(total === 0 ? 0 : 1 + pageSize * (currentPage - 1));
  const rangeEnd = $derived(Math.min(pageSize * currentPage, total));
  const atFirst = $derived(currentPage <= 1);
  const atLast = $derived(currentPage >= pageCount);

  const navButtonClass =
    "inline-flex h-8 w-8 items-center justify-center rounded-lg text-foreground transition-colors hover:bg-accent disabled:opacity-30 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  const showSizeSelector = $derived(pageSizeOptions.length > 0 && onPageSizeChange !== undefined);
</script>

{#if !selectedDataset.isErrored}
  <div class="w-full py-3 flex items-center justify-between gap-4 text-sm text-foreground">
    <!-- Range summary -->
    <span class="text-xs text-muted-foreground tabular-nums whitespace-nowrap">
      {rangeStart.toLocaleString()}–{rangeEnd.toLocaleString()} of {total.toLocaleString()}
      {total === 1 ? "record" : "records"}
    </span>

    <!-- Page navigation -->
    <div class="flex items-center gap-1">
      <button
        class={navButtonClass}
        disabled={atFirst}
        onclick={() => onPageChange(1)}
        aria-label="Go to first page"
      >
        <CaretDoubleLeft size={15} />
      </button>
      <button
        class={navButtonClass}
        disabled={atFirst}
        onclick={() => onPageChange(currentPage - 1)}
        aria-label="Go to previous page"
      >
        <CaretLeft size={15} />
      </button>

      <span class="mx-3 text-xs text-muted-foreground tabular-nums whitespace-nowrap">
        Page <span class="font-bold text-foreground">{currentPage.toLocaleString()}</span>
        of {pageCount.toLocaleString()}
      </span>

      <button
        class={navButtonClass}
        disabled={atLast}
        onclick={() => onPageChange(currentPage + 1)}
        aria-label="Go to next page"
      >
        <CaretRight size={15} />
      </button>
      <button
        class={navButtonClass}
        disabled={atLast}
        onclick={() => onPageChange(pageCount)}
        aria-label="Go to last page"
      >
        <CaretDoubleRight size={15} />
      </button>
    </div>

    <!-- Page size -->
    {#if showSizeSelector}
      <div class="flex items-center gap-2">
        <span class="text-xs text-muted-foreground whitespace-nowrap">Rows per page</span>
        <Select.Root
          type="single"
          value={String(pageSize)}
          items={pageSizeOptions.map((s) => ({ value: String(s), label: String(s) }))}
          onValueChange={(value) => {
            const size = parseInt(value ?? "");
            if (size && size !== pageSize) onPageSizeChange?.(size);
          }}
        >
          <Select.Trigger
            aria-label="Rows per page"
            class="inline-flex h-8 items-center gap-1.5 px-2.5 rounded-lg border border-border bg-background text-xs tabular-nums shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {#snippet children()}
              <span>{pageSize}</span>
              <CaretLeft size={11} class="-rotate-90 text-muted-foreground" />
            {/snippet}
          </Select.Trigger>
          <Select.Portal>
            <Select.Content
              sideOffset={6}
              class="z-50 min-w-[5rem] overflow-hidden rounded-xl border border-border/50 bg-popover/95 p-1 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
            >
              {#each pageSizeOptions as option (option)}
                <Select.Item
                  value={String(option)}
                  label={String(option)}
                  class="cursor-pointer rounded-lg px-2.5 py-1.5 text-xs tabular-nums outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                >
                  {option}
                </Select.Item>
              {/each}
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>
    {:else}
      <!-- Keep the summary left-aligned and the pager centered -->
      <span class="w-24"></span>
    {/if}
  </div>
{/if}
