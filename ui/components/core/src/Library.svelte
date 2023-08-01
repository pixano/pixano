<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  // Imports
  import { createEventDispatcher } from "svelte";

  import DatasetPreviewCard from "./DatasetPreviewCard.svelte";

  import type { Dataset } from "./interfaces";

  // Exports
  export let datasets: Array<Dataset>;
  export let buttonLabel: string;

  const dispatch = createEventDispatcher();

  function handleSelectDataset(dataset: Dataset) {
    dispatch("selectDataset", dataset);
  }
</script>

{#if datasets.length != 0}
  <div class="mx-auto px-8 dark:bg-zinc-800">
    <div
      class="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4"
    >
      {#each datasets as dataset}
        <DatasetPreviewCard
          {dataset}
          {buttonLabel}
          on:selectDataset={() => handleSelectDataset(dataset)}
        />
      {/each}
    </div>
  </div>
{:else}
  <div
    class="mt-4 py-8 flex w-full justify-center font-bold text-lg italic text-zinc-500 dark:text-zinc-300 dark:bg-zinc-800"
  >
    <span style="text-align: center;">
      No datasets found... <br /> <br />
      Please refer to
      <u>
        <a
          href="https://github.com/pixano/pixano/tree/main/notebooks/datasets/import_dataset.ipynb"
          target="_blank"
          class="text-rose-500 dark:text-rose-600
          hover:text-rose-600 dark:hover:text-rose-500"
        >
          this Jupyter notebook
        </a>
      </u>
      for information on how to import your datasets.
    </span>
  </div>
{/if}
