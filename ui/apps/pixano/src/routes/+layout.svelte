<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy, onMount } from "svelte";
  import { fade } from "svelte/transition";

  import { api, checkInferenceStatus, IconButton, initTheme } from "@pixano/core";
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
  import ThemeToggle from "@pixano/core/src/components/ui/theme-toggle/ThemeToggle.svelte";

  import pixanoFavicon from "../assets/favicon.ico";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import {
    currentDatasetStore,
    datasetItemIds,
    datasetsStore,
    datasetTableStore,
    datasetTotalItemsCount,
  } from "../lib/stores/datasetStores";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";

  import "./styles.css";

  let currentDatasetId: string;
  let lastFetchedDatasetId: string;

  const HOME_ROUTE_ID = "/";

  onMount(() => {
    initTheme();
    api
      .getDatasetsInfo()
      .then((loadedDatasetInfos) => {
        datasetsStore.set(loadedDatasetInfos);
      })
      .catch((err) => {
        console.error(err);
      });
    void checkInferenceStatus();
  });

  // Get all the ids of the items of the selected dataset
  $: void getCurrentDatasetItemsIds(currentDatasetId);

  const unsubscribeDatasetTableStore = datasetTableStore.subscribe((value) => {
    if (value.where != undefined) {
      datasetTotalItemsCount.set($datasetItemIds.length);
    }
  });

  const getCurrentDatasetItemsIds = async (datasetId: string) => {
    if (datasetId === undefined || datasetId === lastFetchedDatasetId) return;
    const item_ids = await api.getDatasetItemsIds(datasetId);
    datasetItemIds.set(item_ids);
    datasetTotalItemsCount.set(item_ids.length);
    lastFetchedDatasetId = datasetId;
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

  async function navigateToHome() {
    await goto("/");
  }
</script>

<svelte:head>
  <link rel="icon" type="image/svg" href={pixanoFavicon} />
  <title>Pixano</title>
  <meta name="description" content="Pixano app" />
</svelte:head>

<div class="app h-screen flex flex-col overflow-hidden bg-background text-foreground font-sans">
  <header
    class="w-full h-16 px-6 flex items-center gap-6 bg-card/80 backdrop-blur-[16px] border-b border-border/40 z-50 shrink-0 shadow-glass-sm"
  >
    <div class="flex items-center shrink-0">
      <IconButton
        on:click={navigateToHome}
        tooltipContent="Go to library"
        class="p-1.5 hover:bg-primary/5 rounded-xl transition-all duration-200"
      >
        <img src={pixanoLogo} alt="Logo Pixano" class="w-8 h-8" />
      </IconButton>
    </div>

    <div class="flex-1 h-full">
      {#if $page.route.id !== HOME_ROUTE_ID}
        <div in:fade={{ duration: 300 }} out:fade={{ duration: 200 }} class="h-full w-full">
          <DatasetHeader pageId={$page.route.id} />
        </div>
      {/if}
    </div>

    <div class="flex items-center shrink-0">
      <ThemeToggle />
    </div>
  </header>

  <main class="flex-1 flex flex-col min-h-0 relative bg-background">
    <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
      <slot />
    </div>
  </main>
</div>
