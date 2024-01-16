<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";

  import type { DatasetInfo, DatasetItems } from "@pixano/core/src";
  import { api } from "@pixano/core/src";

  import MainHeader from "../components/layout/MainHeader.svelte";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import { datasetsStore, modelsStore, datasetTableStore } from "../lib/stores/datasetStores";
  import pixanoFavicon from "../assets/favicon.ico";

  import "./styles.css";
  import type { DatasetTableStore } from "$lib/types/pixanoTypes";

  let datasets: DatasetInfo[] = [];
  let models: Array<string>;
  let pageId: string | null;
  let currentDatasetName: string;

  async function handleGetModels() {
    models = await api.getModels();
    modelsStore.set(models);
  }

  async function handleGetDatasets() {
    const loadedDatasets = await api.getDatasets();
    datasets = loadedDatasets ? loadedDatasets : [];

    if (loadedDatasets?.length > 0) {
      datasetsStore.set(loadedDatasets);
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
    let datasetItems: DatasetItems;
    if (query?.search) {
      datasetItems = await api.searchDatasetItems(datasetId, query, page, size);
    } else {
      datasetItems = await api.getDatasetItems(datasetId, page, size);
    }
    datasetsStore.update((value = []) =>
      value.map((dataset) =>
        dataset.id === datasetId ? { ...dataset, page: datasetItems } : dataset,
      ),
    );
  };

  $: page.subscribe((value) => {
    pageId = value.route.id;
    currentDatasetName = value.params.dataset;
  });

  $: {
    const currentDatasetId = datasets?.find((dataset) => dataset.name === currentDatasetName)?.id;
    if (currentDatasetId) getDatasetItems(currentDatasetId).catch((err) => console.error(err));
  }

  datasetTableStore.subscribe((value) => {
    const currentDatasetId = datasets?.find((dataset) => dataset.name === currentDatasetName)?.id;
    if (currentDatasetId && value)
      getDatasetItems(currentDatasetId, value.currentPage, value.pageSize, value.query).catch(
        (err) => console.error(err),
      );
  });
</script>

<svelte:head>
  <link rel="icon" type="image/svg" href={pixanoFavicon} />
</svelte:head>

<div class="app">
  {#if pageId === "/"}
    <MainHeader {datasets} />
  {:else}
    <DatasetHeader datasetName={currentDatasetName} {pageId} {currentDatasetName} />
  {/if}
  <main class="pt-20 h-1 min-h-screen">
    <slot />
  </main>
</div>
