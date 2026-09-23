<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { LayoutProps } from "./$types";
  import { currentDatasetStore } from "$lib/stores/appStores.svelte";

  let { data, children }: LayoutProps = $props();

  $effect(() => {
    currentDatasetStore.value = data.dataset;
  });
</script>

{@render children?.()}
