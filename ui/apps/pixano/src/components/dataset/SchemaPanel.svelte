<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { schemaSections } from "$components/library/import-wizard/wizardUtils";

  import type { InferredSchemaResponse } from "$lib/api/restTypes";

  interface Props {
    schema: InferredSchemaResponse;
  }

  let { schema }: Props = $props();

  const sections = $derived(schemaSections(schema));
  const workspace = $derived(
    schema.workspace && schema.workspace !== "undefined" ? schema.workspace : "",
  );
</script>

<div class="rounded-xl border border-border bg-card p-4">
  <div class="flex items-baseline justify-between">
    <p class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Schema</p>
    {#if workspace}
      <span
        class="rounded-full border border-primary/30 px-2 py-0.5 font-mono text-[10px] text-primary"
      >
        {workspace}
      </span>
    {/if}
  </div>

  <div class="mt-3 space-y-3">
    {#each sections as section (section.title)}
      <div>
        <p class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
          {section.title}
        </p>
        <div class="mt-1 space-y-1">
          {#each section.entries as entry (entry.name)}
            <div class="flex flex-wrap items-center gap-1.5 text-xs">
              <span class="font-medium text-foreground">{entry.name}</span>
              <span
                class="rounded-md border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
              >
                {entry.base}
              </span>
              {#each entry.attrs as attr (attr.name)}
                <span
                  class="rounded-md border border-primary/25 bg-primary/5 px-1.5 py-0.5 font-mono text-[10px] text-foreground/80"
                  title={attr.required ? "required" : undefined}
                >
                  {attr.name}: {attr.type}{attr.collection ? "[]" : ""}{attr.required ? " *" : ""}
                </span>
              {/each}
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>
