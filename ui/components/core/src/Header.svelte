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
  import pixanoLogo from "./assets/pixano.png";

  // Imports
  import { createEventDispatcher } from "svelte";

  import { currentPage } from "../../../apps/explorer/src/stores";
  import type { ItemData } from "../../canvas2d/src/interfaces";
  import { svg_open, svg_save, svg_quit } from "./icons";

  // Exports
  export let app = "";
  export let selectedDataset = null;
  export let selectedItem: ItemData;
  export let save_flag: boolean;

  const dispatch = createEventDispatcher();

  function unselectDataset() {
    selectedDataset = null;
    selectedItem = null;
    currentPage.update((n) => 1);
  }

  function handleSaveClick() {
    dispatch("saveclick");
  }

  function handleCloseClick() {
    dispatch("closeclick");
  }
</script>

<!-- Header -->
<header class="w-full fixed">
  <div
    class="h-20 z-50 py-4 px-4 flex justify-start items-center shrink-0 border-b
    text-zinc-800 dark:text-zinc-300
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500"
  >
    <!-- Logo & app name -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="flex items-center grow space-x-2 font-bold text-3xl">
      <button
        class="flex items-center space-x-2
        hover:text-rose-600 dark:hover:text-rose-500"
        on:click={unselectDataset}
      >
        <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
        <span class="transition-colors"> Pixano {app} </span>
      </button>
      {#if selectedDataset}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-6 w-6"
        >
          <path d={svg_open} fill="currentcolor" />
        </svg>
        <button
          class="hover:text-rose-600 dark:hover:text-rose-500"
          on:click={handleCloseClick}
        >
          <span class="transition-colors">
            {selectedDataset.name}
          </span>
        </button>
        {#if selectedItem}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-6 w-6"
          >
            <path d={svg_open} fill="currentcolor" />
          </svg>
          <span>
            {selectedItem.id}
          </span>
        {/if}
      {/if}
    </div>

    <!-- Navigation -->
    {#if selectedDataset}
      {#if selectedItem && app === "Annotator"}
        <button class="w-30 h pr-4 flex justify-end" on:click={handleSaveClick}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="hover:text-rose-600 dark:hover:text-rose-500 h-8 w-8
            {save_flag ? 'text-rose-500 dark:text-rose-600' : ''}"
          >
            <title>Save</title>
            <path d={svg_save} fill="currentcolor" />
          </svg>
        </button>
      {/if}
      <button
        class="w-30 pr-4 flex justify-end"
        on:click={selectedItem ? handleCloseClick : unselectDataset}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="h-8 w-8 hover:text-rose-600 dark:hover:text-rose-500"
          name="close"
        >
          <title>Close</title>
          <path d={svg_quit} fill="currentcolor" />
        </svg>
      </button>
    {/if}
  </div>
</header>
