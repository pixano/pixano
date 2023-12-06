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
  export let ifNoChoices: string;
  export let choices: Array<string>;
  export let selected: string;

  const dispatch = createEventDispatcher();

  function handleConfirm() {
    dispatch("confirm");
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
      {#if choices}
        <select
          class="py-1 px-2 border rounded focus:outline-none
        bg-slate-100 bg-slate-50 border-slate-300 focus:border-main"
          bind:value={selected}
        >
          {#each choices as choice}
            <option value={choice}>
              {choice}
            </option>
          {/each}
        </select>
      {:else}
        <p class="pb-1 italic">{ifNoChoices}</p>
      {/if}

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
