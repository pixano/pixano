<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import { onMount } from "svelte";

  import type { DatasetInfo } from "@pixano/core/src";
  import { panTool } from "@pixano/dataset-item-workspace/src/lib/settings/selectionTools";
  import {
    modelsUiStore,
    resetColorScale,
    selectedTool,
  } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

  import DatasetPreviewCard from "../../components/dataset/DatasetPreviewCard.svelte";
  import { goto } from "$app/navigation";
  import {
    currentDatasetStore,
    datasetTableStore,
    defaultDatasetTableValues,
  } from "$lib/stores/datasetStores";

  /**
   * DatasetsLibrary Component
   *
   * This component displays a list of datasets. Each dataset is represented by a
   * DatasetPreviewCard component. When a dataset is selected, the user is navigated
   * to the dataset's detail page.
   *
   * Props:
   *   - datasets: Array<DatasetInfo> - An array of dataset information objects.
   *
   * Events:
   *   - selectDataset: Triggered when a dataset is selected.
   */

  export let datasets: Array<DatasetInfo>;

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    currentDatasetStore.set(dataset);
    datasetTableStore.set(defaultDatasetTableValues);
    await goto(`${dataset.id}/dataset`);
  };

  $: visibleDatasets = datasets?.filter((d) => !d.isFiltered) ?? [];

  $: todoDatasets = visibleDatasets.filter((d) => d.bookmarks?.includes("TODO"));
  $: newDatasets = visibleDatasets.filter((d) => d.bookmarks?.includes("NEW"));
  $: favoriteDatasets = visibleDatasets.filter((d) => d.bookmarks?.includes("FAVORITE"));
  $: noBookmarkDatasets = visibleDatasets.filter(
    (d) => !d.bookmarks || d.bookmarks.length === 0,
  );

  onMount(() => {
    resetColorScale();
    //reset interactive segmentation model & table
    modelsUiStore.set({
      currentModalOpen: "none",
      selectedModelName: "",
      selectedTableName: "",
      yetToLoadEmbedding: true,
    });
    //reset Tool
    selectedTool.set(panTool);
  });
</script>

{#if datasets}
  <div class="py-8 px-4 space-y-10">
    <!-- TODO section -->
    {#if todoDatasets.length > 0}
      <section>
        <h2 class="text-xl font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-blue-500 inline-block"></span>
          TODO
        </h2>
        <div class="flex flex-wrap justify-center gap-6">
          {#each todoDatasets as dataset}
            <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
          {/each}
        </div>
      </section>
    {/if}

    <!-- NEW section -->
    {#if newDatasets.length > 0}
      <section>
        <h2 class="text-xl font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-green-500 inline-block"></span>
          NEW
        </h2>
        <div class="flex flex-wrap justify-center gap-6">
          {#each newDatasets as dataset}
            <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
          {/each}
        </div>
      </section>
    {/if}

    <!-- FAVORITE section -->
    {#if favoriteDatasets.length > 0}
      <section>
        <h2 class="text-xl font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-yellow-500 inline-block"></span>
          FAVORITE
        </h2>
        <div class="flex flex-wrap justify-center gap-6">
          {#each favoriteDatasets as dataset}
            <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
          {/each}
        </div>
      </section>
    {/if}

    <!-- Datasets without bookmarks -->
    {#if noBookmarkDatasets.length > 0}
      <section>
        <h2 class="text-xl font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-gray-400 inline-block"></span>
          Autres datasets
        </h2>
        <div class="flex flex-wrap justify-center gap-6">
          {#each noBookmarkDatasets as dataset}
            <DatasetPreviewCard {dataset} on:selectDataset={() => handleSelectDataset(dataset)} />
          {/each}
        </div>
      </section>
    {/if}
  </div>
{:else}
  <div class="flex justify-center py-12">
    <Loader2Icon class="animate-spin" />
  </div>
{/if}
