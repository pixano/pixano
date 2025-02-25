<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
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

  function handleCancel() {
    dispatch("cancel");
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
        bg-slate-100 border-slate-300 focus:border-main"
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
        disabled={!selected || selected === ""}
        class="rounded border border-transparent text-slate-50 mt-3 mx-1 py-1 px-3
        bg-primary transition-colors hover:bg-primary-foreground disabled:bg-primary-light"
        on:click={handleConfirm}
      >
        Ok
      </button>
      <button
        type="button"
        class="rounded border border-transparent text-slate-50 mt-3 mx-1 py-1 px-3
        bg-primary transition-colors hover:bg-primary-foreground"
        on:click={handleCancel}
      >
        Cancel
      </button>
    </div>
  </div>
</div>
