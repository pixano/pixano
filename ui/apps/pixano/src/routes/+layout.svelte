<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { api } from "@pixano/core/src";

  import pixanoFavicon from "../assets/favicon.ico";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import MainHeader from "../components/layout/MainHeader.svelte";
  import {
    currentDatasetStore,
    datasetsStore,
    datasetTableStore,
    defaultDatasetTableValues,
    modelsStore,
  } from "../lib/stores/datasetStores";
  import { page } from "$app/stores";

  import "./styles.css";

  let currentDatasetId: string;
  let currentDatasetItemsIds: string[];

  onMount(() => {
    api
      .getModels()
      .then((models) => modelsStore.set(models))
      .catch(() => modelsStore.set([]));
    api
      .getDatasetsInfo()
      .then((loadedDatasetInfos) => {
        datasetsStore.set(loadedDatasetInfos);
      })
      .catch((err) => {
        console.error(err);
      });
  });

  // Get all the ids of the items of the selected dataset
  $: void getCurrentDatasetItemsIds(currentDatasetId); //void here to avoid .then/.catch. But maybe we could manage error ?

  const getCurrentDatasetItemsIds = async (datasetId: string) => {
    if (datasetId === undefined) return;
    currentDatasetItemsIds = await api.getDatasetItemsIds(datasetId);
  };

  $: page.subscribe((value) => {
    currentDatasetId = value.params.dataset;
    // if currentDatasetStore is not set yet (happens from a refresh on a datasetItem page), set it now
    if (currentDatasetId && $currentDatasetStore == null) {
      const currentDataset = $datasetsStore?.find((dataset) => dataset.id === currentDatasetId);
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
  {#if $page.route.id === "/"}
    <MainHeader datasets={$datasetsStore} />
  {:else}
    <DatasetHeader pageId={$page.route.id} datasetItemsIds={currentDatasetItemsIds} />
  {/if}
  <main class="h-1 min-h-screen bg-slate-50">
    <slot />
  </main>
</div>
