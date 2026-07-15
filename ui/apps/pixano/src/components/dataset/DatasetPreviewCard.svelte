<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowRight, Database, Eye, Shapes, Stack } from "phosphor-svelte";

  import * as api from "$lib/api";
  import { pixanoLogo } from "$lib/assets";
  import { updateDatasetInStore } from "$lib/stores/appStores.svelte";
  import { WorkspaceType, type DatasetInfo } from "$lib/ui";

  /**
   * DatasetPreviewCard Component
   * Improved, professional grade dataset preview with disruptive hover stats.
   */

  interface Props {
    dataset: DatasetInfo;
    onSelectDataset?: () => void;
  }

  let { dataset, onSelectDataset }: Props = $props();

  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  let stats: {
    maxViews: number;
    entities: number;
    annotations: Record<string, number>;
  } | null = $state(null);

  const BOOKMARK_TYPES = ["TODO", "NEW", "FAVORITE"] as const;
  const BOOKMARK_COLORS: Record<string, string> = {
    TODO: "#3B82F6",
    NEW: "#22C55E",
    FAVORITE: "#EAB308",
  };

  function handleSelectDataset() {
    onSelectDataset?.();
  }

  async function toggleBookmark(type: string) {
    try {
      const updated = await api.updateDatasetBookmark(dataset.id, type);
      updateDatasetInStore(dataset.id, { bookmarks: updated.bookmarks });
    } catch (err) {
      console.error("Failed to toggle bookmark", err);
    }
  }

  function handleBookmarkClick(e: MouseEvent, type: string) {
    e.stopPropagation();
    void toggleBookmark(type);
  }

  function isBookmarked(type: string): boolean {
    return dataset.bookmarks.includes(type);
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

  $effect(() => {
    const controller = new AbortController();
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
    return () => controller.abort("aborted");
  });
</script>

<div class="relative group h-full font-sans">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="w-full h-full flex flex-col text-left overflow-hidden bg-card rounded-2xl border border-border shadow-sm hover:shadow-2xl hover:border-primary/30 transition-all duration-500 hover:-translate-y-1.5 group/card cursor-pointer"
    onclick={handleSelectDataset}
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") handleSelectDataset();
    }}
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
              <Eye size={18} class="text-primary-light" />
              <div class="flex flex-col">
                <span class="text-[10px] uppercase tracking-tighter opacity-70 font-bold">
                  Views
                </span>
                <span class="text-xs font-black leading-none">{stats.maxViews}</span>
              </div>
            </div>
            <div class="flex items-center gap-2 text-white/90">
              <Shapes size={18} class="text-primary-light" />
              <div class="flex flex-col">
                <span class="text-[10px] uppercase tracking-tighter opacity-70 font-bold">
                  Entities
                </span>
                <span class="text-xs font-black leading-none">{stats.entities}</span>
              </div>
            </div>
            {#each Object.entries(stats.annotations).slice(0, 2) as [key, val]}
              <div class="flex items-center gap-2 text-white/90">
                <Stack weight="regular" size={18} class="text-primary-light" />
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

      <!-- Bookmark Icons -->
      <div class="absolute top-3 right-3 flex items-center gap-1.5">
        {#each BOOKMARK_TYPES as type (type)}
          {@const active = isBookmarked(type)}
          {@const color = BOOKMARK_COLORS[type]}
          <button
            class="w-7 h-7 rounded-full flex items-center justify-center backdrop-blur-md border transition-all duration-200 hover:scale-110 {active
              ? 'bg-background/80 border-white/20 shadow-lg'
              : 'bg-background/40 border-white/10 opacity-60 hover:opacity-100'}"
            onclick={(e) => handleBookmarkClick(e, type)}
            title={type}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="14"
              viewBox="0 -960 960 960"
              width="14"
              fill={active ? color : "none"}
              stroke={color}
              stroke-width="80"
            >
              <path
                d="M200-120v-640h560v640l-280-120-280 120Zm80-122 200-86 200 86v-478H280v478Z"
              />
            </svg>
          </button>
        {/each}
      </div>

      <!-- Open Indicator -->
      <div
        class="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center opacity-0 group-hover/card:opacity-100 transform translate-x-4 group-hover/card:translate-x-0 transition-all duration-300 shadow-xl"
      >
        <ArrowRight size={20} />
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
          <Database size={17} class="text-primary" />
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
  </div>
</div>
