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
  export let details: string = "";
  export let confirm: string = "Ok";
  export let alternativeAction: string = "";

  const dispatch = createEventDispatcher();

  function handleCancel() {
    dispatch("cancel");
  }
  function handleConfirm() {
    dispatch("confirm");
  }
  function handleAlternativeChoice() {
    dispatch("alternative");
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
        bg-slate-50 text-slate-800"
    >
      <p class="pb-1">{message}</p>
      {#if details}
        <p class="pb-1 italic">{details}</p>
      {/if}
      <button
        type="button"
        class="rounded border mt-3 mx-1 py-1 px-3
        bg-slate-50 transition-colors hover:bg-slate-100 border-slate-300"
        on:click={handleCancel}
      >
        Cancel
      </button>
      {#if alternativeAction}
        <button
          type="button"
          class="rounded border mt-3 mx-1 py-1 px-3
        bg-slate-50 transition-colors hover:bg-slate-100 border-slate-300"
          on:click={handleAlternativeChoice}
        >
          {alternativeAction}
        </button>
      {/if}
      <button
        type="button"
        class="rounded border border-transparent text-slate-50 mt-3 mx-1 py-1 px-3
        bg-primary transition-colors hover:bg-primary-foreground"
        on:click={handleConfirm}
      >
        {confirm}
      </button>
    </div>
  </div>
</div>

<svelte:window on:keydown={handleKeyDown} />
