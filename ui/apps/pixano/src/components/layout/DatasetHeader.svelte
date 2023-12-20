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
    Database,
    ArrowRight,
    ArrowLeft,
    Loader2Icon,
  } from "lucide-svelte";

  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
  import TooltipIconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import PrimaryButton from "@pixano/core/src/lib/components/molecules/PrimaryButton.svelte";
  import type { DatasetInfo } from "@pixano/core/src";
  import { findSelectedItem } from "$lib/api/navigationApi";

  import { datasetsStore, isLoadingNewItemStore } from "../../lib/stores/datasetStores";

  export let datasetName: string;
  export let pageId: string | null;
  export let currentDatasetName: string;

  let datasets: DatasetInfo[];
  let currentItemId: string;
  let isLoading: boolean;

  isLoadingNewItemStore.subscribe((value) => {
    isLoading = value;
  });

  datasetsStore.subscribe((value) => {
    datasets = value;
  });

  $: page.subscribe((value) => {
    currentItemId = value.params.itemId;
  });

  const goToNeighborItem = async (direction: "previous" | "next") => {
    const currentDataset = datasets.find((dataset) => dataset.name === currentDatasetName);
    const datasetItems = Object.values(currentDataset?.page?.items || {});
    const selectedId = findSelectedItem(direction, datasetItems, currentItemId);
    if (selectedId) {
      currentItemId = selectedId;
      await goto(`/${currentDatasetName}/dataset/${selectedId}`);
    }
  };

  const onKeyDown = async (event: KeyboardEvent) => {
    if (event.key === "ArrowLeft") {
      await goToNeighborItem("previous");
    } else if (event.key === "ArrowRight") {
      await goToNeighborItem("next");
    }
    return event.key;
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
      {#if isLoading}
        <Loader2Icon class="animate-spin" />
      {:else}
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
    </div>
  </div>
</header>
<svelte:window on:keyup={onKeyDown} />
