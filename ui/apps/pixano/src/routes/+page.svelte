<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import ModelsPanel from "../components/inference/ModelsPanel.svelte";
  import DatasetsLibrary from "../components/library/DatasetsLibrary.svelte";
  import type { PageProps } from "./$types";

  let { data }: PageProps = $props();

  const isEmpty = $derived(data.datasets && data.datasets.length === 0);
</script>

<div class="h-full flex">
  <div class="flex-1 min-w-0 overflow-y-auto px-6 py-8">
    {#if isEmpty}
      <div class="h-full">
        <DatasetsLibrary datasets={data.datasets} />
      </div>
    {:else}
      <div class="max-w-[1200px] mx-auto">
        <DatasetsLibrary datasets={data.datasets} />
      </div>
    {/if}
  </div>
  <div class="w-80 shrink-0 hidden lg:flex border-l border-border">
    <ModelsPanel />
  </div>
</div>
