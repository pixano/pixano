<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { BaseSchema, TextSpan, type Annotation } from "@pixano/core";

  export let annotations: Annotation[] | undefined;

  const uniqueMentions = (): string[] => {
    const mentions = new Set<string>();
    const textSpans = annotations?.filter((ann) => ann.is_type(BaseSchema.TextSpan)) ?? [];
    (textSpans as TextSpan[]).forEach((tspan) => {
      mentions.add(tspan.data.mention);
    });
    return Array.from(mentions.values());
  };

  const mentions = uniqueMentions();
</script>

{#if annotations?.some((ann) => ann.is_type(BaseSchema.TextSpan))}
  <p class="font-medium mt-4">Text spans</p>
  <div class="grid gap-x-4 gap-y-2 grid-cols-[150px_auto] mt-2 pr-4">
    {#each mentions as mention}
      <p class="font-medium">mention</p>
      <p>{mention}</p>
    {/each}
  </div>
{/if}
