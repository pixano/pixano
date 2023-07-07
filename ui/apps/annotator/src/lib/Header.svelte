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

  // Assets
  import pixanoLogo from "../assets/pixano.png";
  import svg_next from "../assets/icons/next.svg";
  import svg_close from "../assets/icons/close.svg";
  import svg_save from "../assets/icons/save.svg";

  // Imports
  import { createEventDispatcher } from "svelte";

  import { currentPage } from "../stores";
  import type { ItemData } from "../../../../components/Canvas2D/src/interfaces";

  // Exports
  export let selectedDataset = null;
  export let selectedItem: ItemData;
  export let save_flag: boolean;

  const dispatch = createEventDispatcher();

  function unselectDataset() {
    selectedDataset = null;
    selectedItem = null;
    currentPage.update((n) => 1);
  }

  function handleSaveClick() {
    dispatch("saveclick");
  }

  function handleCloseClick() {
    dispatch("closeclick");
  }
</script>

<!-- Header -->
<header class="w-full fixed">
  <div
    class="h-20 py-4 px-4 flex justify-start items-center shrink-0 bg-white border-b-2 dark:bg-zinc-800 dark:border-zinc-700"
  >
    <!-- Logo & app name -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="flex items-center grow space-x-2 font-bold text-3xl">
      <button
        class="cursor-pointer flex items-center space-x-2 hover:text-rose-800 dark:hover:text-rose-300"
        on:click={unselectDataset}
      >
        <img src={pixanoLogo} alt="Logo Pixano" class="w-10" />
        <span class="transition-colors"> Pixano Annotator </span>
      </button>
      {#if selectedDataset}
        <img src={svg_next} alt="icon" class="h-6 w-6 opacity-75" />
        <button class="hover:text-rose-800 dark:hover:text-rose-300">
          <span class="transition-colors">
            {selectedDataset.name}
          </span>
        </button>
        {#if selectedItem}
          <img src={svg_next} alt="icon" class="h-6 w-6 opacity-75" />
          <span>
            {selectedItem.id}
          </span>
        {/if}
      {/if}
    </div>

    <!-- Navigation -->
    {#if selectedDataset}
      {#if selectedItem}
        <button class="w-30 h pr-4 flex justify-end" on:click={handleSaveClick}>
          <img
            src={svg_save}
            alt="icon"
            class="h-8 w-8 cursor-pointer cursor-pointer opacity-75"
            style={save_flag
              ? "background-color: #ffe4e6; box-shadow: 0px 0px 5px 5px #ffe4e6;"
              : ""}
          />
        </button>
      {/if}
      <button
        class="w-30 pr-4 flex justify-end"
        on:click={selectedItem ? handleCloseClick : unselectDataset}
      >
        <img
          src={svg_close}
          alt="icon"
          class="h-8 w-8 cursor-pointer opacity-75"
        />
      </button>
    {/if}
  </div>
</header>
