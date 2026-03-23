<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { modelsUiStore } from "$lib/stores/workspaceStores.svelte";
  import { AiProcessingBadge } from "$lib/ui";

  const currentModalOpen = $derived(modelsUiStore.value.currentModalOpen);
</script>

{#if currentModalOpen === "loading"}
  <AiProcessingBadge overlay message="Loading model..." />
{/if}
