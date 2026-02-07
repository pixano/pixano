<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { createEventDispatcher, onDestroy, onMount } from "svelte";

  import { api, WorkspaceType, type DatasetInfo } from "@pixano/core";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";

  /**
   * DatasetPreviewCard Component
   *
   *   This component displays a preview card for a dataset.
   *   It includes the dataset name, number of items, preview image, and workspace type.
   *   The component also provides a tooltip with additional information about the dataset.
   */

  // Exports
  export let dataset: DatasetInfo;

  let additionalInfo: string | undefined = undefined;
  const controller = new AbortController();

  const dispatch = createEventDispatcher();

  /**
   * Handles the selection of the dataset.
   * Dispatches a "selectDataset" event.
   */
  function handleSelectDataset() {
    dispatch("selectDataset");
  }

  /**
   * Displays the workspace type in a human-readable format.
   * @param {WorkspaceType} workspace - The workspace type to display.
   * @returns {string} - The human-readable workspace type.
   */
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
      case WorkspaceType.UNDEFINED:
        return "Undefined";
    }
  }

  onMount(() => {
    // Get dataset infos to put in tooltip
    api
      .getItemsInfo(dataset.id, null, { signal: controller.signal })
      .then((infos) => {
        if (controller.signal.aborted) return;
        let maxNumViews = 0;
        let entitiesCounts = 0;
        let annCounts: Record<string, number> = {};
        for (const info of infos) {
          // Get max number of views
          maxNumViews = Math.max(maxNumViews, Object.keys(info.info.views).length);
          // Sum objs counts
          if ("info" in info && "entities" in info.info) {
            for (const ent of Object.values(info.info.entities)) {
              entitiesCounts += ent.count;
            }
          }
          for (const [annType, c] of Object.entries(info.info.annotations)) {
            if (!(annType in annCounts)) annCounts[annType] = 0;
            annCounts[annType] += c.count;
          }
        }
        additionalInfo = `Maximum number of views: ${maxNumViews}
        Total number of entities: ${entitiesCounts}
        Total annotation counts:`;
        for (const [k, v] of Object.entries(annCounts)) {
          additionalInfo += `\n${"\xa0".repeat(6)}${k}: ${v}`; // &nbsp; *6 to force some indent space
        }
      })
      .catch((err) => {
        console.log("Error collecting additional dataset infos", err);
      });
  });

  onDestroy(() => {
    controller.abort("aborted");
  });
</script>

<div class="relative group h-full">
  <!-- Tooltip -->
  <div
    class="absolute bottom-full mb-3 w-full bg-foreground text-background text-[11px] leading-relaxed rounded-xl px-4 py-3 shadow-2xl whitespace-pre-line hidden group-hover:block z-20 border border-border/10 animate-in fade-in zoom-in-95 duration-200"
  >
    <div class="font-bold text-xs mb-1 border-b border-background/10 pb-1">{dataset.name}</div>
    {dataset.description}
    {#if additionalInfo}
      <div class="mt-2 pt-2 border-t border-background/10 text-background/70 font-medium">
        {additionalInfo}
      </div>
    {/if}
  </div>

  <button
    class="w-full h-full min-h-[320px] flex flex-col text-left font-DM Sans
    bg-card rounded-2xl border border-border shadow-sm transition-all duration-300 hover:shadow-xl hover:border-primary/20 hover:-translate-y-1 group/btn overflow-hidden"
    on:click={handleSelectDataset}
  >
    <!-- Thumbnail -->
    <div class="relative w-full h-44 bg-muted overflow-hidden">
      <img
        src={dataset.preview ? dataset.preview : pixanoLogo}
        alt="{dataset.name} thumbnail"
        class="w-full h-full object-cover transition-transform duration-500 group-hover/btn:scale-105"
      />
      <div class="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 group-hover/btn:opacity-100 transition-opacity duration-300"></div>
      
      <!-- Workspace Badge (Overlay) -->
      {#if dataset.workspace != WorkspaceType.UNDEFINED}
        <div
          class="absolute top-3 right-3 flex items-center justify-center h-6 px-2.5 rounded-full bg-background/90 backdrop-blur-md text-foreground shadow-sm text-[10px] font-bold uppercase tracking-wider"
        >
          {displayWorkspaceType(dataset.workspace)}
        </div>
      {/if}
    </div>

    <!-- Content -->
    <div class="flex-1 p-5 flex flex-col gap-1">
      <h3 class="text-base font-bold text-foreground line-clamp-1 group-hover/btn:text-primary transition-colors">
        {dataset.name}
      </h3>

      <div class="flex items-center gap-2 mt-auto">
        <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50 border border-border/50">
          <span class="text-[11px] font-bold text-foreground/80 tabular-nums">
            {dataset.num_items}
          </span>
          <span class="text-[10px] text-muted-foreground uppercase tracking-tight font-medium">
            Items
          </span>
        </div>
        
        {#if dataset.size && dataset.size != "Unknown" && dataset.size != "N/A"}
          <span class="text-[11px] text-muted-foreground/60 font-medium">
            • {dataset.size}
          </span>
        {/if}
      </div>
      
      <p class="text-[12px] text-muted-foreground line-clamp-2 mt-2 leading-relaxed opacity-80">
        {dataset.description}
      </p>
    </div>
  </button>
</div>
