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

<div class="mx-auto h-10 w-10">
  <img
    class="h-full w-full object-cover rounded-lg bg-muted"
    src={value}
    alt="record preview"
    loading="lazy"
  />
</div>
