<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { NO_VALUE } from "$lib/statistics/format";

  interface Props {
    /**
     * The record's group in a run of a clustering, or what its column names it — Noise; none —
     * empty, or missing — where the run did not group the record.
     */
    value: number | string | undefined;
  }

  let { value }: Props = $props();
</script>

<!-- A group is a name, not a quantity: shown as it is, never formatted as a number. -->
<div class="min-w-16 px-2 tabular-nums">
  {value === undefined || value === "" ? NO_VALUE : value}
</div>
