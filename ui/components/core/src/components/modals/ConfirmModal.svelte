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
  <div class="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-2xl p-6 max-w-2xl shadow-glass-lg
        bg-card/95 backdrop-blur-[24px] border border-border/40 text-foreground"
    >
      <p class="pb-1">{message}</p>
      {#if details}
        <p class="pb-1 italic text-muted-foreground">{details}</p>
      {/if}
      <button
        type="button"
        class="rounded-lg border mt-3 mx-1 py-1.5 px-4
        bg-background transition-colors hover:bg-accent border-border"
        on:click={handleCancel}
      >
        Cancel
      </button>
      {#if alternativeAction}
        <button
          type="button"
          class="rounded-lg border mt-3 mx-1 py-1.5 px-4
        bg-background transition-colors hover:bg-accent border-border"
          on:click={handleAlternativeChoice}
        >
          {alternativeAction}
        </button>
      {/if}
      <button
        type="button"
        class="rounded-lg border border-transparent text-primary-foreground mt-3 mx-1 py-1.5 px-4
        bg-primary transition-colors hover:bg-primary/80"
        on:click={handleConfirm}
      >
        {confirm}
      </button>
    </div>
  </div>
</div>

<svelte:window on:keydown={handleKeyDown} />
