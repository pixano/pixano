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

{#if selectedDataset.page}
  <div class="h-full flex flex-row bg-slate-50 p-20 gap-4 text-slate-800 font-Montserrat">
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
    <div class="w-full flex flex-col z-10 p-8">
      {#if selectedTab === "source feature"}
        <!-- Overview -->
        <div class="w-full flex flex-row justify-between">
          <div>
            <span class="text-5xl font-bold">
              {selectedDataset.name}
            </span>
            <span class="text-xl text-slate-500">
              #{selectedDataset.id}
            </span>
          </div>
          <div>
            <span class="text-5xl font-bold">
              {selectedDataset.num_elements}
            </span>
            <span class="ml-2 text-xl"> items </span>
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
        <span class="text-5xl font-bold"> Statistics </span>

        {#if selectedDataset.stats != null && selectedDataset.stats.length != 0}
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
      {/if}
    </div>
  </div>
{/if}
