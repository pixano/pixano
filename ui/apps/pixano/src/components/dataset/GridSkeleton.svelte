<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Skeleton } from "$lib/ui";

  interface Props {
    /** Number of skeleton cards (mirror the grid page size, capped for sanity). */
    count?: number;
  }

  let { count = 12 }: Props = $props();

  const items = $derived(Array.from({ length: Math.min(Math.max(count, 6), 24) }, (_, k) => k));
</script>

<div class="w-full h-full overflow-hidden" aria-hidden="true">
  <div
    class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4 p-4"
  >
    {#each items as i (i)}
      <div
        class="flex flex-col overflow-hidden rounded-2xl border border-border bg-card"
        style="opacity: {1 - i * 0.04}"
      >
        <Skeleton class="aspect-square w-full rounded-none" />
        <div class="px-3 py-2.5 flex items-center gap-2">
          <Skeleton class="h-3 flex-1 rounded-full" />
          <Skeleton class="h-3 w-10 rounded-full" />
        </div>
      </div>
    {/each}
  </div>
</div>
