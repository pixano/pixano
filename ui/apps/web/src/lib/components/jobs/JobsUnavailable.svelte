<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  type Props = {
    /** Why, in the server's words: what is missing, and what to do about it. */
    reason: string;
    /** A check is under way, and the button waits for its answer. */
    checking: boolean;
    onCheckAgain: () => void;
  };
  let { reason, checking, onCheckAgain }: Props = $props();
</script>

<section class="flex flex-col gap-2 p-3 text-xs" role="status">
  <h3 class="text-sm font-medium">Jobs are not available on this installation</h3>
  <p class="text-muted-foreground">
    Jobs need a PostgreSQL database, set in PIXANO_DATABASE_URL, and pixano-worker running.
    pixano-worker is not part of the pixano package or image: it comes with the repository's compose
    stack, or is installed from a checkout (docs/running-by-hand.md). The server says:
  </p>
  <p class="whitespace-pre-line break-words rounded bg-muted px-2 py-1">{reason}</p>
  <button
    type="button"
    class="self-start rounded border border-input px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
    disabled={checking}
    onclick={onCheckAgain}
  >
    {checking ? "Checking…" : "Check again"}
  </button>
</section>
