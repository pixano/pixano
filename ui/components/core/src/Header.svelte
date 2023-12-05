<script lang="ts">
  /// <reference types="svelte" />
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
  import { svg_next_page, svg_save, svg_left_arrow, svg_database, svg_dashboard } from "./icons";
  import type { DatasetInfo, DatasetItem } from "./interfaces";
  import pixanoLogo from "./assets/pixano.png";

  // Exports
  export let app: string = "";
  export let selectedDataset: DatasetInfo = null;
  export let selectedItem: DatasetItem;
  export let saveFlag: boolean;
  export let selectedTab: string = null;

  const dispatch = createEventDispatcher();

  function handleUnselectDataset() {
    dispatch("unselectDataset");

    selectedTab = "dashboard";
  }

  function handleUnselectItem() {
    dispatch("unselectItem");
  }

  function handleSaveItemDetails() {
    dispatch("saveItemDetails");
  }

  function selectDatabaseTab() {
    handleUnselectItem();

    selectedTab = "database";
  }

  function selectDashboardTab() {
    handleUnselectItem();

    selectedTab = "dashboard";
  }
</script>

<!-- Header -->
{#if selectedDataset}
  <header class="w-full fixed z-40">
    <div
      class="h-20 p-5 flex justify-start items-center shrink-0
      bg-slate-50 border-b border-slate-300 text-slate-800"
    >
      <!-- Navigation -->
      <div class="h-10 flex items-center grow font-semibold text-2xl">
        <button on:click={handleUnselectDataset} class="h-10 w-10">
          <img src={pixanoLogo} alt="Logo Pixano" class="w-8 h-8 mx-2" />
        </button>
        <div class="h-10 flex mx-2 items-center">
          {#if selectedDataset}
            <button on:click={handleUnselectDataset}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                height="48"
                viewBox="0 -960 960 960"
                width="48"
                class="h-8 w-8 mx-2 p-1 border rounded-full text-slate-800 border-slate-300 hover:bg-slate-300"
              >
                <path d={svg_left_arrow} fill="currentcolor" />
              </svg>
            </button>
            <button on:click={app === "Explorer" ? selectDatabaseTab : handleUnselectDataset}>
              <span class="ml-2">
                {selectedDataset.name}
              </span>
            </button>

            {#if selectedItem}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                height="48"
                viewBox="0 -960 960 960"
                width="48"
                class="h-5 w-5 mx-1"
              >
                <path d={svg_next_page} fill="currentcolor" />
              </svg>
              <span class="truncate">
                {selectedItem.id}
              </span>
            {/if}
          {/if}
        </div>
      </div>

      <!-- Database / Dashboard links -->
      {#if app === "Explorer"}
        <div class="relative h-10 mx-2 flex items-center">
          <button
            class="font-medium h-10 pl-10 pr-6
          {selectedTab === 'database'
              ? 'bg-main rounded-full text-slate-50 hover:bg-secondary'
              : 'bg-slate-50 border border-slate-300 rounded-full text-main hover:bg-slate-300'}"
            on:click={selectDatabaseTab}
          >
            Database
          </button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="absolute left-3 h-5 w-5 pointer-events-none"
          >
            <path d={svg_database} fill={selectedTab === "database" ? "white" : "#771E5F"} />
          </svg>
        </div>

        <div class="relative h-10 mx-2 flex items-center">
          <button
            class="font-medium h-10 pl-10 pr-6
        {selectedTab === 'dashboard'
              ? 'bg-main rounded-full text-slate-50 hover:bg-secondary'
              : 'bg-slate-50 border border-slate-300 rounded-full text-main hover:bg-slate-300'}"
            on:click={selectDashboardTab}
          >
            Dashboard
          </button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="absolute left-3 h-5 w-5 pointer-events-none"
          >
            <path d={svg_dashboard} fill="{selectedTab === 'dashboard' ? 'white' : '#771E5F'} " />
          </svg>
        </div>
      {/if}

      <!-- Save icon -->
      {#if selectedItem && app === "Annotator"}
        <button class="w-30 h px-4 flex justify-end" on:click={handleSaveItemDetails}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-10 w-10 p-1
              {saveFlag ? 'text-main hover:text-secondary' : 'text-slate-500 cursor-default'}"
          >
            <title>Save</title>
            <path d={svg_save} fill="currentcolor" />
          </svg>
        </button>
      {/if}
    </div>
  </header>
{/if}
