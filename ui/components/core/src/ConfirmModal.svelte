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
  import { createEventDispatcher } from "svelte";

  // Exports
  export let message: string;
  export let details: string = "";
  export let confirm: string = "Ok";

  const dispatch = createEventDispatcher();

  function handleCancel() {
    dispatch("cancel");
  }
  function handleConfirm() {
    dispatch("confirm");
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") handleConfirm();
    if (event.key === "Escape") handleCancel();
  }
</script>

<div class="fixed inset-0 z-50 overflow-y-auto">
  <div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-lg p-6 max-w-2xl
        bg-white dark:bg-zinc-800
        text-zinc-800 dark:text-zinc-300"
    >
      <p class="pb-1">{message}</p>
      {#if details}
        <p class="pb-1 italic">{details}</p>
      {/if}
      <button
        type="button"
        class="rounded border mt-3 mx-1 py-1 px-3
        bg-white dark:bg-zinc-800
        hover:bg-zinc-100 dark:hover:bg-zinc-700
        border-zinc-300 dark:border-zinc-600"
        on:click={handleCancel}
      >
        Cancel
      </button>
      <button
        type="button"
        class="rounded border border-transparent text-zinc-50 mt-3 mx-1 py-1 px-3
        bg-rose-500 dark:bg-rose-600
        hover:bg-rose-600 dark:hover:bg-rose-500"
        on:click={handleConfirm}
      >
        {confirm}
      </button>
    </div>
  </div>
</div>

<svelte:window on:keydown={handleKeyDown} />
