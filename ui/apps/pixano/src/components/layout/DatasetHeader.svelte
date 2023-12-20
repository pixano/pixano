<script lang="ts">
  /// <reference types="svelte" />
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  // Imports
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import {
    ArrowLeftCircleIcon,
    Home,
    TrendingUp,
    Database,
    ArrowRight,
    ArrowLeft,
  } from "lucide-svelte";

  import { datasetsStore } from "../../lib/stores/datasetStores";

  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
  import TooltipIconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import PrimaryButton from "@pixano/core/src/lib/components/molecules/PrimaryButton.svelte";
  import type { DatasetInfo, DatasetItem } from "@pixano/core/src";

  export let datasetName: string;
  export let pageId: string | null;
  export let currentDatasetName: string;

  let datasets: DatasetInfo[];

  datasetsStore.subscribe((value) => {
    datasets = value;
  });

  let currentItemId: string;

  $: page.subscribe((value) => {
    currentItemId = value.params.itemId;
  });

  const goToNeighborItem = async (direction: "previous" | "next") => {
    const currentDataset = datasets.find((dataset) => dataset.name === currentDatasetName);
    console.log({ currentDataset });
    if (currentDataset && currentDataset.page) {
      const currentDatasetItems: DatasetItem[] = Object.values(currentDataset.page.items);
      const currentIndex: number = currentDatasetItems.findIndex(
        (item) => item.id === currentItemId,
      );
      if (currentIndex !== -1) {
        const nextIndex = direction === "previous" ? currentIndex - 1 : currentIndex + 1;
        if (nextIndex >= 0 && nextIndex < currentDatasetItems.length) {
          const nextItemId = currentDatasetItems[nextIndex].id;
          await goto(`/${currentDatasetName}/dataset/${nextItemId}`);
        }
      }
    }
  };

  async function navigateTo(route: string) {
    await goto(route);
  }
</script>

<header class="w-full fixed z-40">
  <div
    class="h-20 p-5 flex justify-between items-center shrink-0
      bg-slate-50 border-b border-slate-300 text-slate-800"
  >
    <div class="h-10 flex items-center font-semibold text-2xl">
      <div class="flex gap-4 items-center font-light">
        <button on:click={() => navigateTo("/")} class="h-10 w-10">
          <img src={pixanoLogo} alt="Logo Pixano" class="w-8 h-8 mx-2" />
        </button>
        <TooltipIconButton on:click={() => navigateTo("/")}>
          <ArrowLeftCircleIcon />
        </TooltipIconButton>
        <p>{datasetName}</p>
      </div>
    </div>
    {#if currentItemId}
      <div class="flex items-center gap-4">
        <TooltipIconButton on:click={() => goToNeighborItem("previous")}>
          <ArrowLeft />
        </TooltipIconButton>
        {currentItemId}
        <TooltipIconButton on:click={() => goToNeighborItem("next")}>
          <ArrowRight />
        </TooltipIconButton>
      </div>
    {/if}
    <div class="flex gap-4">
      <PrimaryButton
        isSelected={pageId === "dashboard"}
        on:click={() => navigateTo(`/${datasetName}/dashboard`)}
      >
        <Home strokeWidth={1} />
        Dashboard</PrimaryButton
      >
      <PrimaryButton
        isSelected={pageId === "dataset"}
        on:click={() => navigateTo(`/${datasetName}/dataset`)}
      >
        <Database strokeWidth={1} />
        Dataset</PrimaryButton
      >
      <PrimaryButton
        isSelected={pageId === "stats"}
        on:click={() => navigateTo(`/${datasetName}/stats`)}
      >
        <TrendingUp strokeWidth={1} />
        Stats</PrimaryButton
      >
    </div>
  </div>
</header>
