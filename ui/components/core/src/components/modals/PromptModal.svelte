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
  export let placeholder: string;
  export let input: string;

  const dispatch = createEventDispatcher();

  function handleConfirm() {
    dispatch("confirm");
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") handleConfirm();
  }
</script>

<div class="fixed inset-0 z-50 overflow-y-auto">
  <div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-lg p-6 max-w-2xl
          bg-slate-50 text-slate-800"
    >
      <p class="pb-1">{message}</p>
      <input
        type="text"
        {placeholder}
        class="py-1 px-2 border rounded focus:outline-none
        bg-slate-100 border-slate-300 focus:border-main"
        bind:value={input}
      />
      <button
        type="button"
        class="rounded border border-transparent text-slate-50 mt-3 mx-1 py-1 px-3
        bg-main transition-colors hover:bg-secondary"
        on:click={handleConfirm}
      >
        Ok
      </button>
    </div>
  </div>
</div>

<svelte:window on:keydown={handleKeyDown} />
