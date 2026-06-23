<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Eye } from "lucide-svelte";

  import type { EntityRow } from "$lib/api/annotations.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  interface Props {
    manager: WorkspaceManager;
  }

  let { manager }: Props = $props();

  const entities = $derived<EntityRow[]>(manager.entities);
  // null = all visible; otherwise an entity is "isolated" when it is the only id.
  const showingAll = $derived(manager.visibleEntityIds === null);

  function isIsolated(entityId: string): boolean {
    const visible = manager.visibleEntityIds;
    return visible !== null && visible.size === 1 && visible.has(entityId);
  }

  function resolveCategory(entity: EntityRow): string {
    for (const key of ["category", "label", "class", "name"]) {
      const value = entity[key];
      if (typeof value === "string" && value.length > 0) return value;
    }
    return manager.entitySchemaName ?? "Entity";
  }

  function shortenId(id: string): string {
    return id.length > 16 ? `${id.slice(0, 8)}…${id.slice(-6)}` : id;
  }
</script>

<div class="p-3">
  {#if entities.length === 0}
    <p class="text-xs text-muted-foreground">No entities in this record.</p>
  {:else}
    <div class="mb-2 flex items-center justify-between">
      <p class="text-xs text-muted-foreground">
        {entities.length} entit{entities.length === 1 ? "y" : "ies"}
      </p>
      <button
        type="button"
        onclick={() => manager.showAllEntities()}
        title="Show every entity's annotations"
        class="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] transition-colors {showingAll
          ? 'bg-accent text-accent-foreground'
          : 'text-muted-foreground hover:bg-accent/50'}"
      >
        <Eye class="h-3 w-3" />
        Show all
      </button>
    </div>
    <div class="space-y-1.5">
      {#each entities as entity (entity.id)}
        {@const isolated = isIsolated(entity.id)}
        <button
          type="button"
          onclick={() => manager.toggleEntityVisible(entity.id)}
          title={isolated ? "Click to show all entities" : "Click to show only this entity"}
          class="w-full rounded-md border px-2.5 py-2 text-left transition-colors {isolated
            ? 'border-primary bg-primary/10'
            : 'border-border bg-card hover:bg-accent/40'}"
        >
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
        </button>
      {/each}
    </div>
  {/if}
</div>
