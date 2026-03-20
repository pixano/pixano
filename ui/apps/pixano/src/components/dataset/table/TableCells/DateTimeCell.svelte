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

  const date = $derived.by(() => new Date(value));
</script>

<div class="min-w-24 px-2">
  {date.toLocaleString("fr-FR")}
</div>
