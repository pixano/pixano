<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { LayoutProps } from "./$types";
  import {
    currentDatasetStore,
    datasetItemIds,
    datasetTotalItemsCount,
  } from "$lib/stores/appStores.svelte";

  let { data, children }: LayoutProps = $props();

  $effect(() => {
    currentDatasetStore.value = data.dataset;
    datasetItemIds.value = data.itemIds;
    datasetTotalItemsCount.value = data.itemIds.length;
  });
</script>

{@render children?.()}
