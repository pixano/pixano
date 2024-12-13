<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { BaseSchema, type Annotation } from "@pixano/core";

  export let annotations: Annotation[] | undefined;
</script>

{#if annotations?.some((ann) => ann.is_type(BaseSchema.TextSpan))}
  <p class="font-medium mt-4">Text spans</p>
  <div class="grid gap-x-4 gap-y-2 grid-cols-[150px_auto] mt-2 pr-4">
    {#each annotations?.filter((ann) => ann.is_type(BaseSchema.TextSpan)) ?? [] as textSpan}
      <p class="font-medium">mention</p>
      <p>{textSpan.data.mention}</p>
    {/each}
  </div>
{/if}
