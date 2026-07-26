<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import DatasetsLibrary from "../components/library/DatasetsLibrary.svelte";
  import { datasetsStore } from "$lib/stores/appStores.svelte";

  const isEmpty = $derived(datasetsStore.value && datasetsStore.value.length === 0);
</script>

<div class="h-full overflow-y-auto px-6 py-8">
  {#if isEmpty}
    <div class="h-full">
      <DatasetsLibrary />
    </div>
  {:else}
    <div class="max-w-[1200px] mx-auto">
      <DatasetsLibrary />
    </div>
  {/if}
</div>
