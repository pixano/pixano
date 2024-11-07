<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";
  import { page } from "$app/stores";

  import type { DatasetInfo } from "@pixano/core/src";
  import { api } from "@pixano/core/src";

  import MainHeader from "../components/layout/MainHeader.svelte";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import {
    datasetsStore,
    modelsStore,
    datasetTableStore,
    defaultDatasetTableValues,
    currentDatasetStore,
  } from "../lib/stores/datasetStores";
  import pixanoFavicon from "../assets/favicon.ico";

  import "./styles.css";

  let datasets: Array<DatasetInfo>;
  //let datasetWithFeats: DatasetInfo;
  let pageId: string | null;
  let currentDatasetId: string;
  let currentDatasetItemsIds: string[];

  async function handleGetModels() {
    //TMP for lint
    await new Promise((resolve) => setTimeout(resolve, 1));
    modelsStore.set([]);
    // api
    //   .getModels()
    //   .then((models) => modelsStore.set(models))
    //   .catch((err) => modelsStore.set([]));
  }

  async function handleGetDatasets() {
    try {
      const loadedDatasets = await api.getDatasetsInfo();
      datasets = loadedDatasets;
      datasetsStore.set(loadedDatasets);
    } catch (err) {
      console.error(err);
    }
  }

  onMount(async () => {
    handleGetModels()
      .then(() => console.log(`Found ${$modelsStore.length} model(s):`, $modelsStore))
      .catch((err) => console.error("ERROR: Can't get model", err));
    await handleGetDatasets();
  });

  // Get all the ids of the items of the selected dataset
  $: void getCurrentDatasetItemsIds(currentDatasetId); //void here to avoid .then/.catch. But maybe we could manage error ?

  const getCurrentDatasetItemsIds = async (datasetId: string) => {
    if (datasetId === undefined) return;
    currentDatasetItemsIds = await api.getDatasetItemsIds(datasetId);
  };

  $: page.subscribe((value) => {
    pageId = value.route.id;
    currentDatasetId = value.params.dataset;
    // is currentDatasetStore is not set yet (happens from a refresh), set it now
    // we could probably do better than that, or remove the other currentDatasetStore set ?
    if (currentDatasetId && $currentDatasetStore == null) {
      const currentDataset = datasets?.find((dataset) => dataset.id === currentDatasetId);
      if (currentDataset) {
        currentDatasetStore.set(currentDataset);
      }
    }
  });

  $: {
    currentDatasetStore.subscribe((currentDataset) => {
      if (currentDataset) {
        datasetTableStore.set(defaultDatasetTableValues);
      }
    });
  }
</script>

<svelte:head>
  <link rel="icon" type="image/svg" href={pixanoFavicon} />
  <title>Pixano</title>
  <meta name="description" content="Pixano app" />
</svelte:head>

<div class="app">
  {#if pageId === "/"}
    <MainHeader {datasets} />
  {:else}
    <DatasetHeader {pageId} datasetItemsIds={currentDatasetItemsIds} />
  {/if}
  <main class="h-1 min-h-screen bg-slate-50">
    <slot />
  </main>
</div>
