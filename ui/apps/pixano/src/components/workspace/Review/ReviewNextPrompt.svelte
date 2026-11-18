<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { fly } from "svelte/transition";

  // What Enter offers once nothing is left for the review's keys on the record: a second Enter
  // saves it and opens the next record to review.

  interface Props {
    /** How many annotations are still to review on the record, out of the keys' reach. */
    pendingLeft: number;
  }

  let { pendingLeft }: Props = $props();

  const FLY_DISTANCE_PX = 8;
  const FLY_DURATION_MS = 150;

  const situation = $derived(
    pendingLeft === 0
      ? "Nothing left to review on this record"
      : `${pendingLeft} left to review here, hidden or filtered out`,
  );
</script>

<div
  role="status"
  class="fixed bottom-8 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-border bg-popover px-4 py-3 text-popover-foreground shadow-elevation-2"
  transition:fly={{ y: FLY_DISTANCE_PX, duration: FLY_DURATION_MS }}
>
  <p class="text-xs text-muted-foreground">{situation}</p>
  <p class="mt-1 text-sm font-medium">
    Press <kbd class="rounded border border-border/60 bg-muted/50 px-1.5 font-mono text-xs">
      Enter
    </kbd>
    again to save and go to the next record
    <span class="text-muted-foreground">
      · <kbd class="rounded border border-border/60 bg-muted/50 px-1.5 font-mono text-xs">Esc</kbd>
      to stay
    </span>
  </p>
</div>
