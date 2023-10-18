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

  import pixanoLogo from "./assets/pixano.png";
  import { svg_open, svg_quit, svg_save } from "./icons";

  import type { Dataset, ItemData } from "./interfaces";

  // Exports
  export let app: string = "";
  export let selectedDataset: Dataset = null;
  export let selectedItem: ItemData;
  export let saveFlag: boolean;
  export let nbDatasets: number = 3;
  export let nbItems: number = 3125236;

  const dispatch = createEventDispatcher();

  function handleUnselectDataset() {
    dispatch("unselectDataset");
  }

  function handleUnselectItem() {
    dispatch("unselectItem");
  }

  function handleSaveItemDetails() {
    dispatch("saveItemDetails");
  }
</script>

<!-- Header -->
{#if selectedDataset}
  <header class="w-full fixed z-40">
    <div
      class="h-20 py-4 px-4 flex justify-start items-center shrink-0 border-b
    shadow dark:shadow-zinc-700
    text-zinc-800 dark:text-zinc-300
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-600"
    >
      <!-- Logo & app name -->
      <div class="flex items-center grow space-x-2 font-semibold text-3xl">
        <button
          class="flex items-center space-x-2
        hover:text-rose-600 dark:hover:text-rose-500"
          on:click={handleUnselectDataset}
        >
          <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
          <span class="transition-colors"> Pixano {app} </span>
        </button>
        {#if selectedDataset}
          <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" class="h-6 w-6">
            <path d={svg_open} fill="currentcolor" />
          </svg>
          <button class="hover:text-rose-600 dark:hover:text-rose-500" on:click={handleUnselectItem}>
            <span class="transition-colors">
              {selectedDataset.name}
            </span>
          </button>
          {#if selectedItem}
            <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" class="h-6 w-6">
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
          <button class="w-30 h pr-4 flex justify-end" on:click={handleSaveItemDetails}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8
              {saveFlag ? 'hover:text-rose-600' : 'text-zinc-300 dark:text-zinc-700 cursor-default'}"
            >
              <title>Save</title>
              <path d={svg_save} fill="currentcolor" />
            </svg>
          </button>
        {/if}
        <button class="w-30 pr-4 flex justify-end" on:click={selectedItem ? handleUnselectItem : handleUnselectDataset}>
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
{:else}
  <header class="w-full h-60 px-60 fixed flex flex-col justify-evenly bg-[#771E5F] z-10">
    <!-- Logo & app name -->
    <button class="flex space-x-6" on:click={handleUnselectDataset}>
      <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
      <span class="text-3xl font-bold text-white uppercase text-[Montserrat]"> Pixano {app} </span>
    </button>
    <!-- Infos -->
    <div class="flex flex-row text-white">
      <div class="py-6 px-8 border-2 rounded-lg border-[#872E6F]">
        <span class="text-5xl"> {nbDatasets} </span> <span class="ml-2 text-2xl"> datasets </span>
      </div>
      <div class="ml-8 py-6 px-8 border-2 rounded-lg border-[#872E6F]">
        <span class="text-5xl"> {nbItems} </span> <span class="ml-2 text-2xl"> items </span>
      </div>
      <div class="grow flex flex-row justify-end items-end">
        <input type="text" placeholder="Search" class="h-8 px-4 rounded border-2 border-[#872E6F]" />
      </div>
    </div>
  </header>
{/if}
