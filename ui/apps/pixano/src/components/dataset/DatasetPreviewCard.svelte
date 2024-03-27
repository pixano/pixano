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

  import type { DatasetInfo } from "@pixano/core/src";
  import { svg_right_arrow } from "@pixano/core/src/icons";

  // Exports
  export let dataset: DatasetInfo;

  const dispatch = createEventDispatcher();

  function handleSelectDataset() {
    dispatch("selectDataset");
  }
</script>

<!-- Daisy UI - Version super basique -->
<!-- <button class="card card-compact bg-base-100 shadow-xl" on:click={handleSelectDataset}>
  <div class="card-body">
    <h2 class="card-title">{dataset.name}</h2>
    <p class="text-left">
      {dataset.num_elements} items {dataset.estimated_size && dataset.estimated_size != "N/A"
        ? " - " + dataset.estimated_size
        : ""}
    </p>
  </div>
  <figure>
    <img src={dataset.preview} alt="{dataset.name} thumbnail" />
  </figure>
</button> -->

<!-- Daisy UI - Version un peu améliorée -->
<!-- <button
  class="card card-compact card-bordered bg-base-100 shadow-md hover:shadow-xl"
  on:click={handleSelectDataset}
>
  <div class="card-body">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="48"
      viewBox="0 -960 960 960"
      width="48"
      class="btn btn-sm btn-ghost btn-circle absolute right-5 p-1"
    >
      <path d={svg_right_arrow} fill="currentcolor" />
    </svg>
    <h2 class="card-title text-primary">{dataset.name}</h2>
    <p class="text-left text-info">
      {dataset.num_elements} items {dataset.estimated_size && dataset.estimated_size != "N/A"
        ? " - " + dataset.estimated_size
        : ""}
    </p>
  </div>
  <figure>
    <img src={dataset.preview} alt="{dataset.name} thumbnail" />
  </figure>
</button> -->

<!-- Daisy UI - Version proche de l'originale-->
<!-- <button
  class="card card-compact card-bordered w-96 h-72 bg-base-100 rounded-sm shadow-md hover:shadow-xl"
  on:click={handleSelectDataset}
>
  <div class="card-body">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="24"
      viewBox="0 -960 960 960"
      width="24"
      class="btn btn-sm btn-ghost btn-circle border absolute right-5 p-1"
    >
      <path d={svg_right_arrow} fill="currentcolor" />
    </svg>
    <h2 class="card-title text-primary">{dataset.name}</h2>
    <p class="text-left text-info font-medium">
      {dataset.num_elements} items {dataset.estimated_size && dataset.estimated_size != "N/A"
        ? " - " + dataset.estimated_size
        : ""}
    </p>
    <figure>
      <img src={dataset.preview} alt="{dataset.name} thumbnail" class="w-full h-full object-cover rounded-sm" />
    </figure>
  </div>
</button> -->

<!-- Version Originale -->
<button
  class="w-96 h-72 flex flex-col text-left font-Montserrat
  bg-white rounded-sm shadow shadow-slate-300 transition-shadow hover:shadow-xl"
  on:click={handleSelectDataset}
>
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
      {dataset.num_elements} items {dataset.estimated_size && dataset.estimated_size != "N/A"
        ? " - " + dataset.estimated_size
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

  <div class="m-4 bg-slate-50">
    {#if dataset.preview}
      <img
        src={dataset.preview}
        alt="{dataset.name} thumbnail"
        class="w-[350px] h-[176px] rounded-sm object-contain object-center"
      />
    {/if}
  </div>
</button>
