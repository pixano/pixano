<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { WIZARD_INPUT_CLASS } from "./wizardStyles";
  import type { ImportEmbeddingsOffer } from "$lib/api/restTypes";

  interface Props {
    offer: ImportEmbeddingsOffer;
    /** Queue the embeddings job once the import is done. */
    compute: boolean;
    /** The model the job runs. */
    model: string;
    /** The import is starting: the choice is made. */
    disabled?: boolean;
  }

  let { offer, compute = $bindable(), model = $bindable(), disabled = false }: Props = $props();

  // One wizard is open at a time: the identifiers need not be unique beyond it.
  const DESCRIPTION_ID = "embeddings-after-import-description";
</script>

<section aria-label="After the import" class="rounded-xl border border-border bg-card p-5">
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
    Compute embeddings after the import
  </label>
  {#if offer.available}
    <p id={DESCRIPTION_ID} class="mt-1 text-xs text-muted-foreground">
      Runs in the background once the import is done, for semantic search and “similar to”.
    </p>
    {#if compute}
      <label class="mt-3 block max-w-xs text-xs font-medium text-muted-foreground">
        Model
        <select class="{WIZARD_INPUT_CLASS} mt-1" {disabled} bind:value={model}>
          {#each offer.models as name (name)}<option value={name}>{name}</option>{/each}
        </select>
      </label>
    {/if}
  {:else}
    <p id={DESCRIPTION_ID} class="mt-1 text-xs text-muted-foreground">
      Unavailable: {offer.reason}
    </p>
  {/if}
</section>
