<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Exports
  export let value: string;
</script>

<div class="mx-8 h-20 aspect-square">
  <img class="h-full w-full object-cover rounded" src={value} alt={value} />
</div>
