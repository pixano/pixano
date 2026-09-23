<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Skeleton } from "$lib/ui";

  interface Props {
    /** Number of skeleton rows (mirror the page size, capped for sanity). */
    rows?: number;
    /** Number of scalar columns to mirror (in addition to the thumbnail slot). */
    columns?: number;
  }

  let { rows = 12, columns = 4 }: Props = $props();

  const rowItems = $derived(Array.from({ length: Math.min(Math.max(rows, 3), 25) }, (_, k) => k));
  const colItems = $derived(Array.from({ length: Math.min(Math.max(columns, 1), 8) }, (_, k) => k));
</script>

<div class="w-full h-full overflow-hidden" aria-hidden="true">
  <!-- Header band -->
  <div class="h-11 bg-surface-2 border-b border-border/60 flex items-center gap-6 px-6">
    {#each colItems as j (j)}
      <Skeleton class="h-3 w-20 rounded-full" data-col={j} />
    {/each}
  </div>
  <!-- Rows -->
  {#each rowItems as i (i)}
    <div
      class="h-14 flex items-center gap-6 px-6 border-b border-border/40"
      style="opacity: {1 - i * 0.03}"
    >
      <Skeleton class="h-10 w-10 shrink-0 rounded-lg" />
      {#each colItems as j (j)}
        <Skeleton class="h-3 rounded-full" style="width: {56 + ((i * 37 + j * 53) % 72)}px" />
      {/each}
    </div>
  {/each}
</div>
