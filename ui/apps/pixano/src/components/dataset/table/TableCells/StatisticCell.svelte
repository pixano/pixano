<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { formatStatisticValue } from "$lib/statistics/format";

  interface Props {
    /** The statistic's value for the record; none — empty, or missing — where it has no value. */
    value: number | string | undefined;
  }

  let { value }: Props = $props();
</script>

<div class="min-w-16 px-2 tabular-nums">{formatStatisticValue(value)}</div>
