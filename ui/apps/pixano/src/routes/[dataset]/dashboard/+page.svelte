<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { PageProps } from "./$types";
  import Dashboard from "../../../components/dashboard/Dashboard.svelte";

  let { data }: PageProps = $props();
</script>

{#if data.dataset}
  <div class="pt-20 h-1 min-h-screen">
    <Dashboard selectedDataset={data.dataset} />
  </div>
{/if}
