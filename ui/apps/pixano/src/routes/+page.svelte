<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
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

<DatasetsLibrary {datasets} />
