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
  import { onMount } from "svelte";
  import { currentPage } from "./stores";
  import pixanoLogo from "./assets/pixano.png";
  import Library from "./lib/Library.svelte";
  import EmptyLibrary from "./lib/EmptyLibrary.svelte";
  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import DatasetItemDetails from "./lib/DatasetItemDetails.svelte";
  import * as api from "./lib/api";

  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;
  let selectedItem = null;
  let showDetailsPage: boolean = false;

  async function selectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;
  }

  function selectItem(event: CustomEvent) {
    showDetailsPage = true;
    selectedItem = event.detail.id;
  }

  function goToLibrary() {
    selectedDataset = null;
    selectedItem = null;
    currentPage.update((n) => 1);
  }

  function unselectItem() {
    showDetailsPage = false;
  }

  onMount(async () => {
    datasets = await api.getDatasetsList();
  });
</script>

<!-- Header -->
<header class="w-full fixed">
  <div
    class="h-20 py-4 px-4 flex justify-start items-center bg-white border-b-2 dark:bg-zinc-800 dark:border-zinc-700"
  >
    <!-- Logo & app name -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="flex space-x-4 cursor-pointer hover:text-rose-800 dark:hover:text-rose-300"
      on:click={goToLibrary}
    >
      <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
      <span class="text-3xl font-bold transition-colors">
        Pixano Explorer
      </span>
    </div>
    {#if selectedDataset}
      <span
        class="ml-8 px-2 py-1 flex items-center justify-center bg-zinc-100 text-zinc-600 border rounded-md border-zinc-300 
        dark:bg-zinc-700 dark:text-zinc-300 dark:border-zinc-600"
      >
        {selectedDataset.name}
      </span>
    {/if}

    <!-- Navigation -->
    <div class="mr-4 flex-grow text-right">
      {#if selectedDataset}
        <button
          class="p-2 transition-colors hover:text-rose-800 dark:hover:text-rose-300"
          on:click={goToLibrary}>Back to Library</button
        >
      {/if}
    </div>
  </div>
</header>

<!-- Page offset for header -->
<div class="pt-20" />

{#if !datasets}
  <EmptyLibrary />
{:else if selectedDataset}
  {#if !showDetailsPage}
    <DatasetExplorer dataset={selectedDataset} on:itemclick={selectItem} />
  {:else}
    <DatasetItemDetails
      datasetId={selectedDataset.id}
      rowIndex={selectedItem}
      on:closeclick={unselectItem}
    />
  {/if}
{:else}
  <Library {datasets} on:datasetclick={selectDataset} />
{/if}
