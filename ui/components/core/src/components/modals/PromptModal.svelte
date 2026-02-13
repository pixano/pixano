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
  <div class="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-2xl p-6 max-w-2xl shadow-glass-lg
          bg-card/95 backdrop-blur-[24px] border border-border/40 text-foreground"
    >
      <p class="pb-1">{message}</p>
      <input
        type="text"
        {placeholder}
        class="py-1.5 px-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring
        bg-background border-border"
        bind:value={input}
      />
      <button
        type="button"
        class="rounded-lg border border-transparent text-primary-foreground mt-3 mx-1 py-1.5 px-4
        bg-primary transition-colors hover:bg-primary/80"
        on:click={handleConfirm}
      >
        Ok
      </button>
    </div>
  </div>
</div>

<svelte:window on:keydown={handleKeyDown} />
