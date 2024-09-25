<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { createEventDispatcher } from "svelte";

  import type { DatasetInfo } from "@pixano/core/src";
  import { svg_right_arrow } from "@pixano/core/src/icons";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";

  // Exports
  export let dataset: DatasetInfo;

  const dispatch = createEventDispatcher();

  function handleSelectDataset() {
    dispatch("selectDataset");
  }
</script>

<button
  class="w-96 h-72 flex flex-col text-left font-Montserrat
  bg-white rounded-sm shadow shadow-slate-300 transition-shadow hover:shadow-xl"
  on:click={handleSelectDataset}
>
  <!-- Dataset Infos -->
  <div class="w-full h-1/4 pt-4 px-4 flex flex-col justify-center relative">
    <div>
      <h3
        class="text-lg font-semibold truncate text-primary"
        title="{dataset.name}&#10;&#13;{dataset.description}"
      >
        {dataset.name}
      </h3>
    </div>

    <p class="text-sm text-slate-500 font-medium">
      {dataset.num_items} items {dataset.size && dataset.size != "N/A"
        ? " - " + dataset.size
        : ""}
    </p>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="48"
      viewBox="0 -960 960 960"
      width="48"
      class="absolute right-5 h-8 w-8 mx-auto p-1 border text-slate-800 rounded-full border-slate-300 transition-colors hover:bg-slate-200"
    >
      <path d={svg_right_arrow} fill="currentcolor" />
    </svg>
  </div>

  <!-- Dataset Thumbnail -->
  <div class="m-4 bg-slate-50">
    <img
      src={dataset.preview ?? pixanoLogo}
      alt="{dataset.name} thumbnail"
      class="w-[350px] h-[176px] rounded-sm object-contain object-center"
    />
  </div>
</button>
