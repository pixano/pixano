<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import DatasetsLibrary from "../components/library/DatasetsLibrary.svelte";
  import ModelsPanel from "../components/models/ModelsPanel.svelte";
  import { datasetsStore } from "../lib/stores/datasetStores";
</script>

<div class="h-full flex">
  <!-- Dataset library: scrollable main area -->
  <div class="flex-1 min-w-0 overflow-y-auto px-6 py-8">
    <div class="max-w-[1200px] mx-auto">
      <DatasetsLibrary datasets={$datasetsStore} />
    </div>
  </div>
  <!-- Models sidebar: full height, right edge -->
  <div class="w-80 shrink-0 hidden lg:flex border-l border-border">
    <ModelsPanel />
  </div>
</div>
