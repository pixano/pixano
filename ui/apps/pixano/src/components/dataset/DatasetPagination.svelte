<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetBrowser } from "$lib/ui";
  import { icons } from "$lib/ui";

  interface Props {
    selectedDataset: DatasetBrowser;
    currentPage: number;
    pageSize: number;
    onPageChange: (page: number) => void;
  }

  let { selectedDataset, currentPage, pageSize, onPageChange }: Props = $props();

  function handleGoToFirstPage() {
    if (currentPage > 1) {
      onPageChange(1);
    }
  }

  function handleGoToPreviousPage() {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  }

  function handleGoToNextPage() {
    if (selectedDataset.pagination.total_size > currentPage * pageSize) {
      onPageChange(currentPage + 1);
    }
  }

  function handleGoToLastPage() {
    if (selectedDataset.pagination.total_size > currentPage * pageSize) {
      onPageChange(Math.ceil((selectedDataset.pagination.total_size || 1) / pageSize));
    }
  }
</script>

{#if !selectedDataset.isErrored}
  <div class="w-full py-5 h-20 flex justify-center items-center text-foreground">
    {#if selectedDataset.pagination.total_size > pageSize}
      <button onclick={handleGoToFirstPage} aria-label="Go to first page">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-accent"
        >
          <path d={icons.svg_first_page} fill="currentcolor" />
        </svg>
      </button>

      <button onclick={handleGoToPreviousPage} aria-label="Go to previous page">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-accent"
        >
          <path d={icons.svg_prev_page} fill="currentcolor" />
        </svg>
      </button>
    {/if}

    <span class="mx-4 text-sm font-medium opacity-70">
      {1 + pageSize * (currentPage - 1)} - {Math.min(
        pageSize * currentPage,
        selectedDataset.pagination.total_size,
      )} of
      {selectedDataset.pagination.total_size}
    </span>

    {#if selectedDataset.pagination.total_size > pageSize}
      <button onclick={handleGoToNextPage} aria-label="Go to next page">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-accent"
        >
          <path d={icons.svg_next_page} fill="currentcolor" />
        </svg>
      </button>

      <button onclick={handleGoToLastPage} aria-label="Go to last page">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 p-1 rounded-full transition-colors hover:bg-accent"
        >
          <path d={icons.svg_last_page} fill="currentcolor" />
        </svg>
      </button>
    {/if}
  </div>
{/if}
