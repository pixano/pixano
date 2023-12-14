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

  import type { DatasetInfo } from "./lib/types/datasetTypes";

  // Exports
  export let selectedDataset: DatasetInfo = null;

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
    <div class="w-64 h-fit z-10 flex flex-col items-start">
      <button
        class="w-full h-20 px-8 py-5 text-lg text-left rounded-l-sm
         {selectedTab === 'overview'
          ? 'text-slate-50 bg-main hover:bg-secondary'
          : 'text-main hover:bg-slate-300'}"
        on:click={selectOverviewTab}
      >
        Overview
      </button>
      <button
        class="w-full h-20 px-8 py-5 text-lg text-left rounded-l-sm
        {selectedTab === 'stats'
          ? 'text-slate-50 bg-main hover:bg-secondary '
          : 'text-main hover:bg-slate-300'}"
        on:click={selectStatsTab}
      >
        Statistics
      </button>
    </div>
    <div
      class="w-full z-10 p-8 bg-slate-50 rounded-r-sm border border-slate-300 shadow shadow-slate-300"
    >
      {#if selectedTab === "overview"}
        <!-- Overview -->
        <div class="w-full flex flex-row justify-between">
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
        <!-- Description -->
        <div class="mt-8">
          <p class="text-lg text-justify">
            {selectedDataset.description}
          </p>
        </div>
      {:else if selectedTab === "stats"}
        <!-- Stats -->
        <span class="text-5xl font-bold font-Montserrat"> Statistics </span>

        {#if selectedDataset.stats != null && selectedDataset.stats.length != 0}
          <div class="mt-8 flex flex-wrap justify-center gap-6 mx-8">
            <!-- If charts are ready to be displayed, display them -->
            {#each selectedDataset.stats as chart}
              <Histogram hist={chart} />
            {/each}
          </div>
        {:else}
          <!-- Else show a message -->
          <p class="mt-80 text-slate-500 italic text-center">No statistics found.</p>
        {/if}
      {/if}
    </div>
  </div>
{/if}
