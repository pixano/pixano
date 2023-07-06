<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  import { createEventDispatcher } from "svelte";
  import DatasetPreviewCard from "./DatasetPreviewCard.svelte";

  export let datasets: any;

  const dispatch = createEventDispatcher();

  function handleDatasetClick(dataset) {
    dispatch("datasetclick", { dataset: dataset });
  }
</script>

<div class="mx-auto px-8">
  <div class="grid grid-cols-6 gap-4">
    {#each datasets as dataset}
      <DatasetPreviewCard
        {dataset}
        on:click={() => handleDatasetClick(dataset)}
      />
    {/each}
  </div>
</div>
