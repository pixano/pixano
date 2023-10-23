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
  import type { Dataset } from "./interfaces";
  import Histogram from "./Histogram.svelte";

  // Exports
  export let selectedDataset: Dataset = null;
  export let datasetStats = null;

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
          ? ' text-main bg-slate-200'
          : 'hover:bg-slate-200'}"
        on:click={selectOverviewTab}
      >
        Overview
      </button>
      <button
        class="w-full px-8 py-4 rounded-l-sm text-lg text-left {selectedTab === 'stats'
          ? ' text-main bg-slate-200'
          : 'hover:bg-slate-200'}"
        on:click={selectStatsTab}
      >
        Statistics
      </button>
    </div>
    <div class="w-5/6 p-8 bg-white rounded-r-sm border border-slate-200 shadow shadow-slate-200">
      {#if selectedTab === "overview"}
        <!-- Overview -->
        <div class="w-full mb-16 flex flex-row justify-between">
          <div>
            <span class="text-5xl font-bold font-[Montserrat]"> {selectedDataset.name} </span>
            <span class="text-xl text-slate-400 font-[Montserrat]"> #{selectedDataset.id} </span>
          </div>
          <div>
            <span class="text-5xl font-bold font-[Montserrat]"> {selectedDataset.num_elements} </span>
            <span class="ml-2 text-xl font-[Montserrat]"> items </span>
          </div>
        </div>
        <div class="text-lg text-justify">
          {selectedDataset.description}
          <br />
          <!-- Lorem ipsum -->
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur vel sagittis massa, eu viverra nisl. Donec nibh
          orci, pellentesque quis elit sed, gravida tempus massa. Quisque laoreet, odio vitae iaculis fermentum, nisi erat
          viverra orci, a tristique tortor arcu quis nisl. Duis et orci condimentum, lobortis lacus in, ultricies metus.
          Etiam sed vestibulum nibh. Mauris id nisi consectetur, porttitor odio sed, ullamcorper diam. In pellentesque tristique
          erat, sit amet cursus ante luctus et. Praesent eros velit, convallis vitae pretium ac, tincidunt non metus. Aenean
          facilisis neque eu velit hendrerit auctor. Donec condimentum nulla eu varius gravida. Praesent lacinia nibh nec
          augue vulputate pretium. Nam eu tellus a nisi posuere pharetra at non metus. Duis molestie nec odio nec laoreet.
          Ut commodo, augue eget sagittis egestas, lectus orci cursus velit, et lobortis libero eros non nunc. Suspendisse
          arcu lectus, sodales id maximus eu, dignissim commodo dui. Integer gravida varius mi, et pretium leo dictum sagittis.
          Mauris in arcu eu urna mattis accumsan. Curabitur ultrices, nisl a molestie tempor, ex ipsum tristique sem, fermentum
          porta nisl odio ac sapien. Integer mauris dui, aliquam et euismod nec, congue vel nulla. Proin accumsan molestie
          ipsum at venenatis. Pellentesque aliquet sapien justo, a euismod velit sagittis fringilla. Maecenas at ornare arcu,
          et ullamcorper ligula.
        </div>
      {:else if selectedTab === "stats"}
        <!-- Stats -->
        <span class="text-5xl font-bold font-[Montserrat]"> STATISTICS </span>
        {#if datasetStats != null && datasetStats.length != 0}
          <div class="mt-16 grid grid-cols-3 gap-16">
            <!-- If charts are ready to be displayed, display them -->
            {#each datasetStats as chart}
              <Histogram hist={chart} />
            {/each}
          </div>
        {:else}
          <!-- Else show a message -->
          <p class="mt-80 text-slate-500 italic text-center ">
            Sorry, no statistics are available for this dataset. Did you forget to include them ?
          </p>
        {/if}
      {/if}
    </div>
  </div>
{/if}
