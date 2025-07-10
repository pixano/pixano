<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Dashboard from "../../../components/dashboard/Dashboard.svelte";
  import { currentDatasetStore } from "$lib/stores/datasetStores";
</script>

{#if $currentDatasetStore}
  <div class="pt-20 h-1 min-h-screen">
    <Dashboard selectedDataset={$currentDatasetStore} />
  </div>
{/if}
