<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { ImportStatisticsOffer } from "$lib/api/restTypes";

  interface Props {
    offer: ImportStatisticsOffer;
    /** Queue the statistics job once the import is done. */
    compute: boolean;
    /** The import is starting: the choice is made. */
    disabled?: boolean;
  }

  let { offer, compute = $bindable(), disabled = false }: Props = $props();

  // One wizard is open at a time: the identifier need not be unique beyond it.
  const DESCRIPTION_ID = "statistics-after-import-description";
</script>

<section
  aria-label="Statistics after the import"
  class="rounded-xl border border-border bg-card p-5"
>
  <label
    class="inline-flex items-center gap-2 text-sm font-medium text-foreground {offer.available
      ? 'cursor-pointer'
      : 'cursor-not-allowed opacity-60'}"
  >
    <input
      type="checkbox"
      class="size-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      aria-describedby={DESCRIPTION_ID}
      disabled={disabled || !offer.available}
      bind:checked={compute}
    />
    Compute statistics after the import
  </label>
  {#if offer.available}
    <p id={DESCRIPTION_ID} class="mt-1 text-xs text-muted-foreground">
      Runs in the background once the import is done, for a dataset holding objects, boxes or masks:
      how many each record holds, and the share of its image each object's boxes cover.
    </p>
  {:else}
    <p id={DESCRIPTION_ID} class="mt-1 text-xs text-muted-foreground">
      Unavailable: {offer.reason}
    </p>
  {/if}
</section>
