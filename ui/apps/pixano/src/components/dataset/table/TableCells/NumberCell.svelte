<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  
  interface Props {
    // Exports
    value: number;
  }

  let { value }: Props = $props();
</script>

<div class="min-w-16 px-2">{value}</div>
