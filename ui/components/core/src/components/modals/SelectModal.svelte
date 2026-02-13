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
  <div class="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-2xl p-6 max-w-2xl shadow-glass-lg
          bg-card/95 backdrop-blur-[24px] border border-border/40 text-foreground"
    >
      <p class="pb-1">{message}</p>
      {#if choices}
        <select
          class="py-1.5 px-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring
        bg-background border-border"
          bind:value={selected}
        >
          {#each choices as choice}
            <option value={choice}>
              {choice}
            </option>
          {/each}
        </select>
      {:else}
        <p class="pb-1 italic text-muted-foreground">{ifNoChoices}</p>
      {/if}

      <button
        type="button"
        disabled={!selected}
        class="rounded-lg border border-transparent text-primary-foreground mt-3 mx-1 py-1.5 px-4
        bg-primary transition-colors hover:bg-primary/80 disabled:opacity-50"
        on:click={handleConfirm}
      >
        Ok
      </button>
      <button
        type="button"
        class="rounded-lg border border-transparent text-primary-foreground mt-3 mx-1 py-1.5 px-4
        bg-primary transition-colors hover:bg-primary/80"
        on:click={handleCancel}
      >
        Cancel
      </button>
    </div>
  </div>
</div>
