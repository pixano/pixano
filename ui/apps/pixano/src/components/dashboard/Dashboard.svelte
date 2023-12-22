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
  import type { DatasetInfo } from "@pixano/core/src";
  import { cn } from "@pixano/core/src/lib/utils";

  import Histogram from "./Histogram.svelte";
  import { dashboardTabs } from "../../lib/constants/dashboardsConstants";

  // Exports
  export let selectedDataset: DatasetInfo;

  let selectedTab: (typeof dashboardTabs)[number] = dashboardTabs[0];
</script>

{#if selectedDataset.page}
  <div class="h-full flex flex-row bg-slate-50 p-8 gap-4">
    <div class="bg-white min-h-[70%] shadow-md flex flex-col w-[30%]">
      {#each dashboardTabs as tab}
        <button
          on:click={() => (selectedTab = tab)}
          class={cn("p-4 text-left first-letter:capitalize hover:bg-slate-100", {
            "bg-slate-200 text-primary hover:bg-slate-200": tab === selectedTab,
          })}>{tab}</button
        >
      {/each}
    </div>
    <div class="w-full z-10 p-8">
      {#if selectedTab === "source feature"}
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
      {:else if selectedTab === "derived source feature"}
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
