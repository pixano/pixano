<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { PageProps } from "./$types";
  import DatasetsLibrary from "../components/library/DatasetsLibrary.svelte";
  import ModelsPanel from "../components/inference/ModelsPanel.svelte";

  let { data }: PageProps = $props();
</script>

<div class="h-full flex">
  <!-- Dataset library: scrollable main area -->
  <div class="flex-1 min-w-0 overflow-y-auto px-6 py-8">
    <div class="max-w-[1200px] mx-auto">
      <DatasetsLibrary datasets={data.datasets} />
    </div>
  </div>
  <!-- Models sidebar: full height, right edge -->
  <div class="w-80 shrink-0 hidden lg:flex border-l border-border">
    <ModelsPanel />
  </div>
</div>
