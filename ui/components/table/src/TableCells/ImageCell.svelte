<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Exports
  export let value: string;
</script>

<div class="mx-4 h-16 aspect-square">
  <img class="h-full w-full object-cover rounded-lg" src={value} alt={value} loading="lazy" />
</div>
