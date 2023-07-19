<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  // Imports
  import { createEventDispatcher } from "svelte";
  import DatasetPreviewCard from "./DatasetPreviewCard.svelte";

  // Exports
  export let datasets: any;
  export let btn_label: string;

  const dispatch = createEventDispatcher();

  function handleDatasetClick(dataset) {
    dispatch("datasetclick", { dataset: dataset });
  }
</script>

{#if datasets.length != 0}
  <div class="mx-auto px-8">
    <div
      class="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4"
    >
      {#each datasets as dataset}
        <DatasetPreviewCard
          {dataset}
          {btn_label}
          on:click={() => handleDatasetClick(dataset)}
        />
      {/each}
    </div>
  </div>
{:else}
  <div
    class="mt-4 py-8 flex w-full justify-center font-bold text-lg italic text-zinc-500 dark:text-zinc-300"
  >
    <span style="text-align: center;">
      No datasets found... <br /> <br />
      Please refer to
      <u>
        <a
          href="https://github.com/pixano/pixano/tree/main/notebooks/dataset/import_dataset.ipynb"
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
