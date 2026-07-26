<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    // Exports
    value: string;
  }

  let { value }: Props = $props();
</script>

<div class="min-w-24 max-w-[280px] px-2 truncate mx-auto" title={value}>
  {value}
</div>
