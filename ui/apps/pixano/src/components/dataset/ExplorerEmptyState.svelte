<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { MagnifyingGlass } from "phosphor-svelte";

  interface Props {
    /** Whether a filter / search / find-similar query is narrowing the result set. */
    hasActiveQuery: boolean;
    onClear?: () => void;
  }

  let { hasActiveQuery, onClear }: Props = $props();
</script>

<div class="flex-1 flex flex-col items-center justify-center gap-4 py-20 px-6 text-center">
  <div class="w-20 h-20 rounded-2xl bg-primary/5 flex items-center justify-center">
    <MagnifyingGlass weight="thin" size={44} class="text-primary/40" />
  </div>
  <div class="space-y-1.5">
    <h2 class="text-2xl font-bold text-foreground">
      {hasActiveQuery ? "No matching records" : "No records yet"}
    </h2>
    <p class="text-sm text-muted-foreground max-w-md">
      {hasActiveQuery
        ? "Nothing matches the current filters and search. Loosen or clear them to see records again."
        : "This dataset has no records to display."}
    </p>
  </div>
  {#if hasActiveQuery && onClear}
    <button
      type="button"
      onclick={onClear}
      class="h-11 px-6 rounded-xl bg-primary text-primary-foreground text-sm font-bold uppercase tracking-widest shadow-sm hover:bg-primary/90 active:scale-95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      Clear filters
    </button>
  {/if}
</div>
