<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy, onMount } from "svelte";

  import { api, cn } from "@pixano/core/src";

  import pixanoFavicon from "../assets/favicon.ico";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import MainHeader from "../components/layout/MainHeader.svelte";
  import {
    currentDatasetStore,
    datasetItemIds,
    datasetsStore,
    datasetTableStore,
    datasetTotalItemsCount,
    modelsStore,
  } from "../lib/stores/datasetStores";
  import { page } from "$app/stores";

  import "./styles.css";

  let currentDatasetId: string;

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

  const unsubscribeDatasetTableStore = datasetTableStore.subscribe((value) => {
    if (value.where != undefined) {
      datasetTotalItemsCount.set($datasetItemIds.length);
    }
  });

  const getCurrentDatasetItemsIds = async (datasetId: string) => {
    if (datasetId === undefined) return;
    if ($datasetItemIds.length === 0) {
      const item_ids = await api.getDatasetItemsIds(datasetId);
      datasetItemIds.set(item_ids);
      datasetTotalItemsCount.set($datasetItemIds.length);
    } else {
      datasetTotalItemsCount.set($datasetItemIds.length);
    }
  };

  $: unsubscribePage = page.subscribe((value) => {
    currentDatasetId = value.params.dataset;
    // if currentDatasetStore is not set yet (happens from a refresh on a datasetItem page), set it now
    if (currentDatasetId && $currentDatasetStore == null) {
      const currentDataset = $datasetsStore?.find((dataset) => dataset.id === currentDatasetId);
      if (currentDataset) {
        currentDatasetStore.set(currentDataset);
      }
    }
  });

  onDestroy(() => {
    unsubscribeDatasetTableStore();
    unsubscribePage();
  });
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
    <DatasetHeader pageId={$page.route.id} />
  {/if}
  <main
    class={cn("bg-slate-50 flex flex-col h-screen", $page.route.id !== HOME_ROUTE_ID && "pt-20")}
  >
    <slot />
  </main>
</div>
