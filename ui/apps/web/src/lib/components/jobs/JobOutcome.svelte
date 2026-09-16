<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { QuarantinedItem } from "$lib/api/jobs";

  type Props = {
    /** The outcome in words, or null while the job runs. */
    summary: string | null;
    quarantined: number;
    /** The quarantine, once asked for. */
    items: QuarantinedItem[] | undefined;
    onShowQuarantine: () => void;
  };
  let { summary, quarantined, items, onShowQuarantine }: Props = $props();
</script>

{#if summary}
  <div class="flex flex-col gap-1">
    <span class="text-xs text-muted-foreground">{summary}</span>
    {#if quarantined > 0}
      {#if items}
        <ul class="flex flex-col gap-0.5 rounded bg-muted p-2">
          {#each items as item (item.item_id)}
            <li class="flex items-baseline justify-between gap-2 text-xs">
              <span class="truncate font-mono">{item.item_id}</span>
              <span class="shrink-0 text-muted-foreground">{item.reason}</span>
            </li>
          {/each}
          {#if items.length < quarantined}
            <li class="text-xs text-muted-foreground">
              …and {quarantined - items.length} more
            </li>
          {/if}
        </ul>
      {:else}
        <button
          type="button"
          class="self-start rounded border border-input px-2 py-1 text-xs hover:bg-muted"
          onclick={onShowQuarantine}
        >
          Show quarantine
        </button>
      {/if}
    {/if}
  </div>
{/if}
