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
  import { svg_right_arrow } from "@pixano/core/src/icons";

  // Exports
  export let dataset: DatasetInfo;

  let additionalInfo: string | undefined = undefined;
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
      case WorkspaceType.UNDEFINED:
        return "Undefined";
    }
  }

  onMount(() => {
    //get dataset infos to put in tooltip
    api
      .getItemsInfo(dataset.id, null, { signal: controller.signal })
      .then((infos) => {
        if (controller.signal.aborted) return;
        let maxNumViews = 0;
        let entitiesCounts = 0;
        let annCounts: Record<string, number> = {};
        for (const info of infos) {
          //get max number of views
          maxNumViews = Math.max(maxNumViews, Object.keys(info.info.views).length);
          //sum objs counts
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
          additionalInfo += `\n${"\xa0".repeat(6)}${k}: ${v}`; //&nbsp; *6 to force some indent space
        }
      })
      .catch((err) => {
        console.log("Error collecting additionnal dataset infos", err);
      });
  });

  onDestroy(() => {
    controller.abort("aborted");
  });
</script>

<div class="relative group w-96">
  <!-- Tooltip -->
  <div
    class="absolute bottom-full mb-2 w-96 bg-gray-800 text-white text-sm rounded-md px-4 py-2 shadow-lg whitespace-pre-line hidden group-hover:block z-10"
  >
    Name: {dataset.name}
    Description: {dataset.description}
    {additionalInfo ? `\n\n${additionalInfo}` : ""}
  </div>

  <button
    class="w-96 h-72 flex flex-col text-left font-Montserrat
    bg-white rounded-sm shadow shadow-slate-300 transition-shadow hover:shadow-xl"
    on:click={handleSelectDataset}
  >
    <!-- Infos -->
    <div class="w-full h-1/4 pt-4 px-4 flex flex-col justify-center relative">
      <h3 class="text-lg w-5/6 font-semibold truncate text-primary">
        {dataset.name}
      </h3>

      <p class="text-sm text-slate-500 font-medium">
        {dataset.num_items} item{dataset.num_items > 1 ? "s" : ""}
        {dataset.size && dataset.size != "Unknown" && dataset.size != "N/A"
          ? " - " + dataset.size
          : ""}
      </p>

      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="absolute right-5 h-8 w-8 mx-auto p-1 border text-slate-800 rounded-full border-slate-300 transition-colors hover:bg-slate-200"
      >
        <path d={svg_right_arrow} fill="currentcolor" />
      </svg>
    </div>

    <!-- Thumbnail -->
    <div class="m-4 bg-slate-50 flex items-center justify-center">
      <img
        src={dataset.preview ? dataset.preview : pixanoLogo}
        alt="{dataset.name} thumbnail"
        class="w-[350px] h-[150px] rounded-sm object-contain object-center"
      />
    </div>

    <!-- Workspace -->
    {#if dataset.workspace != WorkspaceType.UNDEFINED}
      <div
        class="mt-auto mb-2 mx-auto flex items-center justify-center h-10 px-6 border rounded-full"
      >
        {displayWorkspaceType(dataset.workspace)}
      </div>
    {/if}
  </button>
</div>
