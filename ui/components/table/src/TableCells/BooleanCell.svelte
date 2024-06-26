<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Exports
  export let value: boolean;
</script>

<input type="checkbox" disabled={true} class="px-4 pointer-events: none;" bind:checked={value} />
