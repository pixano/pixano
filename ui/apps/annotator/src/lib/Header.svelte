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

  // Assets
  import pixanoLogo from "../assets/pixano.png";

  // Imports
  import { currentPage } from "../stores";
  import type { ItemData } from "../../../../components/Canvas2D/src/interfaces";

  export let selectedDataset = null;

  export let selectedItem: ItemData;

  function goToLibrary() {
    selectedDataset = null;
    selectedItem = null;
    currentPage.update((n) => 1);
  }
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
        Pixano Annotator
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
          on:click={goToLibrary}
        >
          Back to Library
        </button>
      {/if}
    </div>
  </div>
</header>
