<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Exports
  export let value: string;

  const date = new Date(value);
</script>

<div class="min-w-24 px-2">
  {date.toLocaleString("fr-FR")}
</div>
