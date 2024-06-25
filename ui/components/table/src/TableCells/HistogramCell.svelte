<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Histogram } from "@pixano/core";

  import type { DatasetStat } from "@pixano/core";

  // Exports
  export let value: DatasetStat;
</script>

<div class="mx-8 h-24">
  <Histogram hist={value} minimal={true} />
</div>
