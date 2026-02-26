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
    datasetSchema.value = data.schema;
    sourcesStore.value = data.sources;
    datasetItemIds.value = data.itemIds;
    datasetTotalItemsCount.value = data.itemIds.length;
  });
</script>

{@render children?.()}
