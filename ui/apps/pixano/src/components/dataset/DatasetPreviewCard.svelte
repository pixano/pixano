<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowRight, Database, Eye, Layers, Shapes } from "lucide-svelte";
  import { createEventDispatcher, onDestroy, onMount } from "svelte";

  import { api, WorkspaceType, type DatasetInfo } from "@pixano/core";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";

  /**
   * DatasetPreviewCard Component
   * Improved, professional grade dataset preview with disruptive hover stats.
   */

  // Exports
  export let dataset: DatasetInfo;

  let stats: {
    maxViews: number;
    entities: number;
    annotations: Record<string, number>;
  } | null = null;

  const controller = new AbortController();
  const dispatch = createEventDispatcher();

  function handleSelectDataset() {
    dispatch("selectDataset");
  }

  function displayWorkspaceType(workspace: WorkspaceType) {
    switch (workspace) {
      case WorkspaceType.IMAGE:
        return "Image";
      case WorkspaceType.VIDEO:
        return "Video";
      case WorkspaceType.IMAGE_VQA:
        return "VQA";
      case WorkspaceType.IMAGE_TEXT_ENTITY_LINKING:
        return "Entity Linking";
      case WorkspaceType.PCL_3D:
        return "3D";
      default:
        return "General";
    }
  }

  onMount(() => {
    api
      .getDatasetStats(dataset.id, { signal: controller.signal })
      .then((groupStats) => {
        if (controller.signal.aborted) return;
        const viewTables = groupStats["views"] || {};
        const entityTables = groupStats["entities"] || {};
        const annTables = groupStats["annotations"] || {};

        stats = {
          maxViews: Object.keys(viewTables).length,
          entities: Object.values(entityTables).reduce((a, b) => a + b, 0),
          annotations: annTables,
        };
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          console.log("Error collecting additional dataset infos", err);
        }
      });
  });

  onDestroy(() => {
    controller.abort("aborted");
  });
</script>

<div class="relative group h-full font-sans">
  <button
    class="w-full h-full flex flex-col text-left overflow-hidden bg-card rounded-2xl border border-border shadow-sm hover:shadow-2xl hover:border-primary/30 transition-all duration-500 hover:-translate-y-1.5 group/card"
    on:click={handleSelectDataset}
  >
    <div class="relative aspect-video w-full overflow-hidden bg-muted">
      <img
        src={dataset.preview || pixanoLogo}
        alt="{dataset.name} thumbnail"
        class="w-full h-full object-cover transition-transform duration-700 group-hover/card:scale-110"
      />

      <div
        class="absolute inset-0 bg-black/40 backdrop-blur-[2px] opacity-0 group-hover/card:opacity-100 transition-all duration-300 flex flex-col justify-end p-4"
      >
        {#if stats}
          <div
            class="grid grid-cols-2 gap-3 transform translate-y-4 group-hover/card:translate-y-0 transition-transform duration-500 delay-75"
          >
            <div class="flex items-center gap-2 text-white/90">
              <Eye size={14} class="text-primary-light" />
              <div class="flex flex-col">
                <span class="text-[10px] uppercase tracking-tighter opacity-70 font-bold">
                  Views
                </span>
                <span class="text-xs font-black leading-none">{stats.maxViews}</span>
              </div>
            </div>
            <div class="flex items-center gap-2 text-white/90">
              <Shapes size={14} class="text-primary-light" />
              <div class="flex flex-col">
                <span class="text-[10px] uppercase tracking-tighter opacity-70 font-bold">
                  Entities
                </span>
                <span class="text-xs font-black leading-none">{stats.entities}</span>
              </div>
            </div>
            {#each Object.entries(stats.annotations).slice(0, 2) as [key, val]}
              <div class="flex items-center gap-2 text-white/90">
                <Layers size={14} class="text-primary-light" />
                <div class="flex flex-col">
                  <span
                    class="text-[10px] uppercase tracking-tighter opacity-70 font-bold line-clamp-1"
                  >
                    {key}
                  </span>
                  <span class="text-xs font-black leading-none">{val}</span>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="flex items-center justify-center h-full">
            <div
              class="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin"
            ></div>
          </div>
        {/if}
      </div>

      <!-- Category Badge -->
      {#if dataset.workspace !== WorkspaceType.UNDEFINED}
        <div
          class="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-background/80 backdrop-blur-md border border-white/10 shadow-lg"
        >
          <span class="text-[10px] font-black uppercase tracking-widest text-foreground/90">
            {displayWorkspaceType(dataset.workspace)}
          </span>
        </div>
      {/if}

      <!-- Open Indicator -->
      <div
        class="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center opacity-0 group-hover/card:opacity-100 transform translate-x-4 group-hover/card:translate-x-0 transition-all duration-300 shadow-xl"
      >
        <ArrowRight size={16} />
      </div>
    </div>

    <!-- Info Section -->
    <div class="flex-1 p-5 flex flex-col min-h-0">
      <div class="flex items-start justify-between gap-2 mb-1.5">
        <h3
          class="text-base font-black text-foreground tracking-tight line-clamp-1 group-hover/card:text-primary transition-colors"
        >
          {dataset.name}
        </h3>
      </div>

      <p
        class="text-[13px] text-muted-foreground line-clamp-2 leading-relaxed opacity-80 mb-4 flex-1"
      >
        {dataset.description || "No description provided for this dataset."}
      </p>

      <!-- Footer Meta -->
      <div class="flex items-center gap-4 pt-4 border-t border-border/40">
        <div class="flex items-center gap-1.5">
          <Database size={13} class="text-primary" />
          <span class="text-xs font-bold text-foreground tabular-nums">{dataset.num_items}</span>
          <span class="text-[10px] font-bold text-muted-foreground uppercase tracking-tight">
            Items
          </span>
        </div>
        {#if dataset.size && dataset.size !== "Unknown" && dataset.size !== "N/A"}
          <div class="h-1 w-1 rounded-full bg-border"></div>
          <div class="flex items-center gap-1.5 text-muted-foreground">
            <span class="text-xs font-medium uppercase tracking-tighter">{dataset.size}</span>
          </div>
        {/if}
      </div>
    </div>
  </button>
</div>
