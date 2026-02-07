<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetInfo } from "@pixano/core";
  import { cn, Histogram } from "@pixano/core";

  import { dashboardTabs } from "../../lib/constants/dashboardsConstants";

  // Exports
  export let selectedDataset: DatasetInfo;

  let selectedTab: (typeof dashboardTabs)[number] = dashboardTabs[0];
</script>

<div class="h-full flex flex-row bg-background p-20 gap-6 text-foreground font-DM Sans">
  <div
    class="bg-card min-h-[70%] rounded-xl border border-border flex flex-col w-1/6 min-w-32 overflow-hidden"
  >
    {#each dashboardTabs as tab}
      <button
        on:click={() => (selectedTab = tab)}
        class={cn("p-4 text-left first-letter:capitalize hover:bg-accent transition-colors", {
          "bg-muted text-foreground font-medium": tab === selectedTab,
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
        <span class="text-4xl font-semibold truncate" title={selectedDataset.name}>
          {selectedDataset.name}
          <br />
          <span class="text-lg text-muted-foreground font-normal">
            #{selectedDataset.id}
          </span>
        </span>
        <span class="w-1/4 ml-8 text-4xl font-semibold text-right">
          {selectedDataset.num_items}
          <span class="text-lg font-normal">item{selectedDataset.num_items > 1 ? "s" : ""}</span>
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
        <p class="mt-80 text-muted-foreground italic text-center">No statistics found.</p>
      {/if}
    {:else}
      <!-- Else show a message -->
      <p class="mt-80 text-muted-foreground italic text-center">No statistics found.</p>{/if}
  </div>
</div>
