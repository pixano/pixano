<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { createEventDispatcher, onDestroy, onMount } from "svelte";

  import { api, WorkspaceType, type DatasetInfo, type SplitStatusCount } from "@pixano/core/src";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
  import {
    svg_bookmark_filled,
    svg_bookmark_outline,
    svg_right_arrow,
  } from "@pixano/core/src/icons";
  import { updateDatasetInStore } from "$lib/stores/datasetStores";

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
  let splitData: SplitStatusCount[] = [];
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

    // Get split / status distribution
    api
      .getDatasetSplits(dataset.id)
      .then((data) => {
        if (controller.signal.aborted) return;
        splitData = data;
      })
      .catch((err) => {
        console.log("Error collecting split data", err);
      });
  });

  const BOOKMARK_TYPES = ["TODO", "NEW", "FAVORITE"] as const;

  const bookmarkColors: Record<string, string> = {
    TODO: "#3B82F6",
    NEW: "#22C55E",
    FAVORITE: "#EAB308",
  };

  const statusColors: Record<string, string> = {
    done: "#22C55E",
    validated: "#22C55E",
    todo: "#EF4444",
    review: "#EAB308",
    inReview: "#EAB308",
    wip: "#3B82F6",
    inProgress: "#3B82F6",
  };

  function colorForStatus(s: string): string {
    return statusColors[s] ?? "#94A3B8";
  }

  $: groupedSplits = (() => {
    const map = new Map<string, { statuses: { status: string; count: number; pct: number }[] }>();
    const splitTotals = new Map<string, number>();
    for (const row of splitData) {
      splitTotals.set(row.split, (splitTotals.get(row.split) ?? 0) + row.count);
    }
    for (const row of splitData) {
      if (!map.has(row.split)) {
        map.set(row.split, { statuses: [] });
      }
      const total = splitTotals.get(row.split) ?? 1;
      map.get(row.split)!.statuses.push({
        status: row.status,
        count: row.count,
        pct: Math.round((row.count / total) * 100),
      });
    }
    return [...map.entries()].map(([name, v]) => ({ name, ...v }));
  })();

  async function toggleBookmark(bookmark: string) {
    const updated = await api.updateDatasetBookmark(dataset.id, bookmark);
    if (updated) {
      updateDatasetInStore(dataset.id, { bookmarks: updated.bookmarks });
    }
  }

  onDestroy(() => {
    controller.abort("aborted");
  });
</script>

<div class="relative group w-96">
  <!-- Info overlay (appears on hover at half height) -->
  <div
    class="absolute left-2 right-2 top-full mt-1 bg-white text-gray-800 text-sm rounded-md px-4 py-3 shadow-[0_12px_50px_rgba(0,0,0,0.45)] border border-slate-300 whitespace-pre-line hidden group-hover:block z-10"
  >
    <span class="font-semibold">{dataset.name}</span>
    <br />
    {dataset.description}
    {#if additionalInfo}
      <hr class="my-1 border-slate-200" />
      {additionalInfo}
    {/if}
    {#if splitData.length > 0}
      <hr class="my-1 border-slate-200" />
      <table class="w-full text-xs text-left">
        <thead>
          <tr class="text-slate-400 font-medium">
            <th class="pr-2">Split</th>
            <th class="pr-2">Status</th>
            <th class="pr-2 text-right">Count</th>
          </tr>
        </thead>
        <tbody>
          {#each splitData as row}
            <tr class="text-slate-700">
              <td class="pr-2 font-medium">{row.split}</td>
              <td class="pr-2">{row.status}</td>
              <td class="pr-2 text-right">{row.count}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

    <button
    class="w-96 flex flex-col text-left font-Montserrat
    bg-white rounded-sm shadow shadow-slate-300 transition-shadow hover:shadow-xl"
    on:click={handleSelectDataset}
  >
    <!-- Infos + bookmarks + arrow -->
    <div class="w-full h-1/4 pt-4 px-4 flex flex-col justify-center relative">
      <div class="flex items-start">
        <!-- Title and stats -->
        <div class="w-5/6">
          <h3 class="text-lg font-semibold truncate text-primary">
            {dataset.name}
          </h3>
          <p class="text-sm text-slate-500 font-medium">
            {dataset.num_items} item{dataset.num_items > 1 ? "s" : ""}
            {dataset.size && dataset.size != "Unknown" && dataset.size != "N/A"
              ? " - " + dataset.size
              : ""}
          </p>
          {#if dataset.creation_date}
            <p class="text-xs text-slate-400">
              Créé le {dataset.creation_date}
            </p>
          {/if}
        </div>

        <!-- Right area: bookmarks horizontally + arrow below -->
        <div class="flex flex-col items-center ml-auto">
          <div class="flex flex-row gap-1">
            {#each BOOKMARK_TYPES as btype}
              <button
                title={btype}
                class="w-7 h-7 flex items-center justify-center rounded-full transition-colors hover:bg-slate-100"
                style="color: {bookmarkColors[btype]}"
                on:click|stopPropagation={() => toggleBookmark(btype)}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="20"
                  viewBox="0 -960 960 960"
                  width="20"
                >
                  <path
                    d={dataset.bookmarks.includes(btype) ? svg_bookmark_filled : svg_bookmark_outline}
                    fill="currentcolor"
                  />
                </svg>
              </button>
            {/each}
          </div>

          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="mt-1 h-8 w-8 mx-auto p-1 border text-slate-800 rounded-full border-slate-300 transition-colors hover:bg-slate-200"
          >
            <path d={svg_right_arrow} fill="currentcolor" />
          </svg>
        </div>
      </div>
    </div>

    <!-- Thumbnail -->
    <div class="m-4 bg-slate-50 flex items-center justify-center">
      <img
        src={dataset.preview ? dataset.preview : pixanoLogo}
        alt="{dataset.name} thumbnail"
        class="w-[350px] h-[150px] rounded-sm object-contain object-center"
      />
    </div>

    <!-- Split / status progress bars -->
    {#if splitData.length > 0}
      <div class="px-4 pt-1 space-y-1">
        {#each groupedSplits as split}
          <div class="flex items-center gap-2 text-xs">
            <span class="w-8 font-medium text-slate-500 truncate">{split.name}</span>
            <div
              class="flex-1 h-2.5 rounded-full bg-slate-100 overflow-hidden flex"
              title={split.statuses.map((s) => `${s.status}: ${s.count} (${s.pct}%)`).join(", ")}
            >
              {#each split.statuses as s}
                <div
                  style="width: {s.pct}%; background: {colorForStatus(s.status)}"
                  class="h-full transition-all"
                  title="{s.status}: {s.count}"
                ></div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}

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
