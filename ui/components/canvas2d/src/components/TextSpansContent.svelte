<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { BaseSchema, TextSpan, type Annotation } from "@pixano/core";
  import { DISPLAY_MENTION_FEATURES } from "@pixano/dataset-item-workspace/src/lib/settings/defaultFeatures";

  export let annotations: Annotation[] | undefined;

  const uniqueMentions = (): [string, string][] => {
    const mentions: [string, string][] = [];
    const textSpans = annotations?.filter((ann) => ann.is_type(BaseSchema.TextSpan)) ?? [];
    (textSpans as TextSpan[]).forEach((tspan) => {
      let mention_label: string = "mention";
      for (const feat of DISPLAY_MENTION_FEATURES) {
        if (feat in tspan.data && typeof tspan.data[feat] === "string") {
          mention_label = tspan.data[feat];
          break;
        }
      }
      if (!mentions.find(([ml, m]) => ml === mention_label && m === tspan.data.mention))
        mentions.push([mention_label, tspan.data.mention]);
    });
    return Array.from(mentions.values());
  };

  const mentions = uniqueMentions();
</script>

{#if annotations?.some((ann) => ann.is_type(BaseSchema.TextSpan))}
  <p class="font-medium mt-4">Text spans</p>
  <div class="grid gap-x-4 gap-y-2 grid-cols-[150px_auto] mt-2 pr-4">
    {#each mentions as [mention_label, mention]}
      <p class="font-medium ml-4">{mention_label}</p>
      <p>{mention}</p>
    {/each}
  </div>
{/if}
