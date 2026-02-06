<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { createEventDispatcher, onDestroy, onMount } from "svelte";

  import { api, WorkspaceType, type DatasetInfo } from "@pixano/core/src";
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

<div class="relative group">
  <!-- Tooltip -->
  <div
    class="absolute bottom-full mb-2 w-full bg-foreground text-background text-sm rounded-lg px-4 py-2 shadow-lg whitespace-pre-line hidden group-hover:block z-10"
  >
    Name: {dataset.name}
    Description: {dataset.description}
    {additionalInfo ? `\n\n${additionalInfo}` : ""}
  </div>

  <button
    class="w-full h-72 flex flex-col text-left font-DM Sans
    bg-card rounded-xl border border-border shadow-sm transition-all duration-200 hover:shadow-lg hover:border-foreground/10"
    on:click={handleSelectDataset}
  >
    <!-- Infos -->
    <div class="w-full pt-4 px-4 flex flex-col justify-center">
      <h3 class="text-base font-medium truncate text-foreground">
        {dataset.name}
      </h3>

      <p class="text-sm text-muted-foreground">
        {dataset.num_items} item{dataset.num_items > 1 ? "s" : ""}
        {dataset.size && dataset.size != "Unknown" && dataset.size != "N/A"
          ? " - " + dataset.size
          : ""}
      </p>
    </div>

    <!-- Thumbnail -->
    <div class="m-4 rounded-lg overflow-hidden bg-muted flex items-center justify-center">
      <img
        src={dataset.preview ? dataset.preview : pixanoLogo}
        alt="{dataset.name} thumbnail"
        class="w-[350px] h-[150px] rounded-lg object-contain object-center"
      />
    </div>

    <!-- Workspace -->
    {#if dataset.workspace != WorkspaceType.UNDEFINED}
      <div
        class="mt-auto mb-3 mx-auto flex items-center justify-center h-7 px-3 rounded-full bg-muted text-muted-foreground text-xs"
      >
        {displayWorkspaceType(dataset.workspace)}
      </div>
    {/if}
  </button>
</div>
