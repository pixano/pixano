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
  import DatasetsLibrary from "../components/library/DatasetsLibrary.svelte";
  import type { DatasetInfo } from "@pixano/core/src";
  import { datasetsStore } from "../lib/stores/datasetStores";

  let datasets: Array<DatasetInfo>;

    datasetsStore.subscribe((value) => {
    if (value) {
      datasets = value;
    }
  });
</script>

<svelte:head>
  <title>Pixano</title>
  <meta name="description" content="Pixano app" />
</svelte:head>

<DatasetsLibrary {datasets} />
