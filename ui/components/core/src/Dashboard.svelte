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
  import Histogram from "./Histogram.svelte";

  import type { Dataset, Stats } from "./lib/types/interfaces";

  // Exports
  export let selectedDataset: Dataset = null;
  export let datasetStats: Array<Stats> = null;

  let selectedTab: string = "overview";

  function selectOverviewTab() {
    selectedTab = "overview";
  }

  function selectStatsTab() {
    selectedTab = "stats";
  }
</script>

<!-- Dashboard -->
{#if selectedDataset.page}
  <div class="h-full flex flex-row">
    <div class="w-1/6 flex flex-col items-start">
      <button
        class="w-full px-8 py-4 rounded-l-sm text-lg text-left {selectedTab === 'overview'
          ? ' text-main bg-slate-300'
          : 'hover:bg-slate-300'}"
        on:click={selectOverviewTab}
      >
        Overview
      </button>
      <button
        class="w-full px-8 py-4 rounded-l-sm text-lg text-left {selectedTab === 'stats'
          ? ' text-main bg-slate-300'
          : 'hover:bg-slate-300'}"
        on:click={selectStatsTab}
      >
        Statistics
      </button>
    </div>
    <div class="w-5/6 p-8 bg-slate-50 rounded-r-sm border border-slate-300 shadow shadow-slate-300">
      {#if selectedTab === "overview"}
        <!-- Overview -->
        <div class="w-full mb-16 flex flex-row justify-between">
          <div>
            <span class="text-5xl font-bold font-Montserrat">
              {selectedDataset.name}
            </span>
            <span class="text-xl text-slate-500 font-Montserrat">
              #{selectedDataset.id}
            </span>
          </div>
          <div>
            <span class="text-5xl font-bold font-Montserrat">
              {selectedDataset.num_elements}
            </span>
            <span class="ml-2 text-xl font-Montserrat"> items </span>
          </div>
        </div>
        <div class="text-lg text-justify">
          {selectedDataset.description}
        </div>
      {:else if selectedTab === "stats"}
        <!-- Stats -->
        <span class="text-5xl font-bold font-Montserrat"> STATISTICS </span>
        {#if datasetStats != null && datasetStats.length != 0}
          <div class="mt-16 grid grid-cols-3 gap-16">
            <!-- If charts are ready to be displayed, display them -->
            {#each datasetStats as chart}
              <Histogram hist={chart} />
            {/each}
          </div>
        {:else}
          <!-- Else show a message -->
          <p class="mt-80 text-slate-500 italic text-center">
            Sorry, no statistics are available for this dataset. Did you forget to include them ?
          </p>
        {/if}
      {/if}
    </div>
  </div>
{/if}
