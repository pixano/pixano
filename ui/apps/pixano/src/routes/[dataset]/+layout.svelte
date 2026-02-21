<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { LayoutProps } from "./$types";
  import {
    currentDatasetStore,
    datasetSchema,
    sourcesStore,
    datasetItemIds,
    datasetTotalItemsCount,
  } from "$lib/stores/appStores.svelte";

  let { data, children }: LayoutProps = $props();

  // Populate existing stores for backward compatibility
  $effect(() => {
    currentDatasetStore.value = data.dataset;
  });
  $effect(() => {
    datasetSchema.value = data.schema;
  });
  $effect(() => {
    sourcesStore.value = data.sources;
  });
  $effect(() => {
    datasetItemIds.value = data.itemIds;
    datasetTotalItemsCount.value = data.itemIds.length;
  });
</script>

{@render children?.()}
