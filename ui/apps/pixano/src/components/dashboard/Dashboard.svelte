<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetInfo } from "@pixano/core/src";
  import { cn, Histogram } from "@pixano/core/src";

  import { dashboardTabs } from "../../lib/constants/dashboardsConstants";

  // Exports
  export let selectedDataset: DatasetInfo;

  let selectedTab: (typeof dashboardTabs)[number] = dashboardTabs[0];
</script>

<div class="h-full flex flex-row bg-slate-50 p-20 gap-4 text-slate-800 font-Montserrat">
  <div class="bg-white min-h-[70%] shadow-md flex flex-col w-1/6 min-w-32">
    {#each dashboardTabs as tab}
      <button
        on:click={() => (selectedTab = tab)}
        class={cn("p-4 text-left first-letter:capitalize hover:bg-slate-100", {
          "bg-slate-200 text-primary hover:bg-slate-200": tab === selectedTab,
        })}
      >
        {tab}
      </button>
    {/each}
  </div>
  <div class="w-3/4 flex flex-col z-10 p-8">
    {#if selectedTab === "source feature"}
      <!-- Overview -->
      <div class="w-full flex justify-between">
        <span class="text-5xl font-bold truncate" title={selectedDataset.name}>
          {selectedDataset.name}
          <br />
          <span class="text-xl text-slate-500">
            #{selectedDataset.id}
          </span>
        </span>
        <span class="w-1/4 ml-8 text-5xl font-bold text-right">
          {selectedDataset.num_items}
          <span class="text-xl">item{selectedDataset.num_items > 1 ? "s" : ""}</span>
        </span>
      </div>

      <!-- Description -->
      <div class="mt-8">
        <p class="text-lg text-justify">
          {selectedDataset.description}
        </p>
      </div>
    {:else if selectedTab === "derived source feature"}
      <!-- Stats -->
      {#if selectedDataset.stats != null && selectedDataset.stats.length != 0}
        <span class="text-5xl font-bold">Statistics</span>
        <div class="mt-6 h-full overflow-y-auto flex flex-wrap justify-between gap-6">
          <!-- If charts are ready to be displayed, display them -->
          {#each selectedDataset.stats as chart}
            <div class="w-[47%] min-h-80">
              <Histogram hist={chart} />
            </div>
          {/each}
        </div>
      {:else}
        <!-- Else show a message -->
        <p class="mt-80 text-slate-500 italic text-center">No statistics found.</p>
      {/if}
    {:else}
      <!-- Else show a message -->
      <p class="mt-80 text-slate-500 italic text-center">No statistics found.</p>{/if}
  </div>
</div>
