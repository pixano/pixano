<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetStat } from "$lib/types/dataset";
  import { Histogram } from "$lib/ui";

  interface Props {
    // Exports
    value: DatasetStat;
  }

  let { value }: Props = $props();
</script>

<div class="mx-8 h-24">
  <Histogram hist={value} minimal={true} />
</div>
