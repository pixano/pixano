<script lang="ts">
  /**
    @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
    @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
    @license CECILL-C
  
    This software is a collaborative computer program whose purpose is to
    generate and explore labeled data for computer vision applications.
    This software is governed by the CeCILL-C license under French law and
    abiding by the rules of distribution of free software. You can use, 
    modify and/ or redistribute the software under the terms of the CeCILL-C
    license as circulated by CEA, CNRS and INRIA at the following URL
  
    http://www.cecill.info
    */

  // Imports
  import { currentPage } from "../stores";
  import type { ItemData } from "./interfaces";

  export let selectedDataset = null;

  export let selectedItem: ItemData;

  function goToLibrary() {
    selectedDataset = null;
    selectedItem = null;
    currentPage.update((n) => 1);
  }
</script>

<!-- Header -->
<header class="fixed w-full px-96 bg-gradient-to-t from-[#EC5F66] to-[#751D5F] z-10">
  <div class="h-20 py-4 px-4 flex justify-start items-center">
    <!-- Logo & app name -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="flex space-x-4 cursor-pointer hover:text-rose-800" on:click={goToLibrary}>
      <img src="pixano_white.svg" alt="Logo Pixano" class="h-10" />
    </div>

    <!-- Navigation -->
    <div class="mr-4 flex-grow text-right">
      {#if selectedDataset}
        <button class="p-2 text-white transition-colors hover:text-rose-100" on:click={goToLibrary}
          >Back to Library</button
        >
      {/if}
    </div>
  </div>
</header>
