<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";

  import type { DatasetItems, DatasetInfo, ExplorerData } from "@pixano/core/src";
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
  import type { DatasetTableStore } from "$lib/types/pixanoTypes";

  let datasets: Array<DatasetInfo>;
  let datasetWithFeats: DatasetInfo;
  let models: Array<string>;
  let pageId: string | null;
  let currentDatasetName: string;

  async function handleGetModels() {
    models = await api.getModels();
    modelsStore.set(models);
  }

  async function handleGetDatasets() {
    try {
      const loadedDatasets = await api.getDatasets();
      datasets = loadedDatasets;
      datasetsStore.set(loadedDatasets);
    } catch (err) {
      console.error(err);
    }
  }

  onMount(async () => {
    await handleGetDatasets();
    await handleGetModels();
  });

  const getDatasetItems = async (
    datasetId: string,
    page?: number,
    size?: number,
    query?: DatasetTableStore["query"],
  ) => {
    let datasetItems: ExplorerData = {
      id: "",
      name: "",
      table_data: { cols: [], rows: [] },
      pagination: { total: 0, current: 0, size: 0 },
      sem_search: [],
    };
    let isErrored = false;
    if (query?.search) {
      // try {
      //   datasetItems = await api.searchDatasetItems(datasetId, query, page, size);
      // } catch (err) {
      //   isErrored = true;
      // }
    } else {
      try {
        datasetItems = await api.getDatasetItems(datasetId, page, size);
        //datasetWithFeats = await api.getDataset(datasetId);
      } catch (err) {
        isErrored = true;
      }
    }
    datasetsStore.update((value = []) =>
      value.map((dataset) =>
        dataset.id === datasetId
          ? {
              ...datasetItems,
              //features_values: datasetWithFeats.features_values,
              //page: datasetItems,
              isErrored,
            }
          : dataset,
      ),
    );
  };

  $: page.subscribe((value) => {
    pageId = value.route.id;
    currentDatasetName = value.params.dataset;
  });

  $: {
    currentDatasetStore.subscribe((currentDataset) => {
      if (currentDataset) {
        datasetTableStore.set(defaultDatasetTableValues);
      }
    });
  }

  datasetTableStore.subscribe((value) => {
    const currentDatasetId = datasets?.find((dataset) => dataset.name === currentDatasetName)?.id;
    if (currentDatasetId && value) {
      getDatasetItems(currentDatasetId, value.currentPage, value.pageSize, value.query).catch(
        (err) => console.error(err),
      );
    }
  });
</script>

<svelte:head>
  <link rel="icon" type="image/svg" href={pixanoFavicon} />
</svelte:head>

<div class="app">
  {#if pageId === "/"}
    <MainHeader {datasets} />
  {:else}
    <DatasetHeader {pageId} />
  {/if}
  <main class="h-1 min-h-screen bg-slate-50">
    <slot />
  </main>
</div>
