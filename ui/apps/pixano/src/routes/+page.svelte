<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import DatasetsLibrary from "../components/library/DatasetsLibrary.svelte";
  import { datasetsStore } from "../lib/stores/datasetStores";
</script>

<DatasetsLibrary datasets={$datasetsStore} />
