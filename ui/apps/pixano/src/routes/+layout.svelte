<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { api, cn } from "@pixano/core/src";

  import pixanoFavicon from "../assets/favicon.ico";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import MainHeader from "../components/layout/MainHeader.svelte";
  import {
    currentDatasetStore,
    datasetsStore,
    datasetTableStore,
    datasetTotalItemsCount,
    defaultDatasetTableValues,
    modelsStore,
  } from "../lib/stores/datasetStores";
  import { page } from "$app/stores";

  import "./styles.css";

  let currentDatasetId: string;
  let currentDatasetItemsIds: string[];

  const HOME_ROUTE_ID = "/";

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

  datasetTableStore.subscribe(async (value) => {
    if (value.where != undefined) {
      currentDatasetItemsIds = await api.getDatasetItemsIds(currentDatasetId, value.where);
      datasetTotalItemsCount.set(currentDatasetItemsIds.length);
    }
  });

  const getCurrentDatasetItemsIds = async (datasetId: string) => {
    if (datasetId === undefined) return;
    currentDatasetItemsIds = await api.getDatasetItemsIds(datasetId);
    datasetTotalItemsCount.set(currentDatasetItemsIds.length);
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
  {#if $page.route.id === HOME_ROUTE_ID}
    <MainHeader datasets={$datasetsStore} />
  {:else}
    <DatasetHeader pageId={$page.route.id} datasetItemsIds={currentDatasetItemsIds} />
  {/if}
  <main
    class={cn("bg-slate-50 flex flex-col h-screen", $page.route.id !== HOME_ROUTE_ID && "pt-20")}
  >
    <slot />
  </main>
</div>
