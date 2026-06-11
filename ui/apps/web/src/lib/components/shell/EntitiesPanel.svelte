<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { EntityRow } from "$lib/api/annotations.js";

  interface Props {
    entities: EntityRow[];
    entitySchemaName: string | null;
  }

  let { entities, entitySchemaName }: Props = $props();

  function resolveCategory(entity: EntityRow): string {
    for (const key of ["category", "label", "class", "name"]) {
      const value = entity[key];
      if (typeof value === "string" && value.length > 0) return value;
    }
    return entitySchemaName ?? "Entity";
  }

  function shortenId(id: string): string {
    return id.length > 16 ? `${id.slice(0, 8)}…${id.slice(-6)}` : id;
  }
</script>

<div class="p-3">
  {#if entities.length === 0}
    <p class="text-xs text-muted-foreground">No entities in this record.</p>
  {:else}
    <p class="mb-2 text-xs text-muted-foreground">{entities.length} entit{entities.length === 1 ? "y" : "ies"}</p>
    <div class="space-y-1.5">
      {#each entities as entity (entity.id)}
        <div class="rounded-md border border-border bg-card px-2.5 py-2">
          <div class="flex items-center gap-2">
            <span
              class="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
            >
              {resolveCategory(entity)}
            </span>
            <span class="min-w-0 truncate font-mono text-[10px] text-muted-foreground">
              {shortenId(entity.id)}
            </span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
