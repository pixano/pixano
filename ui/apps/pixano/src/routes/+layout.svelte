<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";

  import type { DatasetInfo } from "@pixano/core/src";

  import { api } from "@pixano/core/src";

  import MainHeader from "../components/layout/MainHeader.svelte";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import { datasets as datasetsStore } from "../lib/stores/datasetStores";

  import "./styles.css";

  let datasets: DatasetInfo[] = [];
  let models: Array<string>;
  let pageId: string | null;
  let datasetName: string;

  async function handleGetModels() {
    console.log("App.handleGetModels");

    const start = Date.now();
    models = await api.getModels();
    console.log("App.handleGetModels - api.getModels in", Date.now() - start, "ms", models);
  }

  async function handleGetDatasets() {
    const loadedDatasets = await api.getDatasets();
    datasets = loadedDatasets ? loadedDatasets : [];

    if (datasets?.length > 0) {
      datasetsStore.set(datasets);
    }
  }

  onMount(async () => {
    await handleGetDatasets();
    await handleGetModels();
  });

  const handleSearch = () => {
    console.log("App.handleSearch");
  };

  $: page.subscribe((value) => {
    pageId = value.route.id;
    datasetName = value.params.dataset;
  });
</script>

<div class="app">
  {#if pageId === "/"}
    <MainHeader {datasets} on:input={handleSearch} />
  {:else}
    <DatasetHeader {datasetName} {pageId} />
  {/if}
  <main>
    <slot />
  </main>
</div>
