<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { QuarantinedItem } from "$lib/api/jobsApi";
  import { recordOf } from "$lib/stores/jobsStore.svelte";

  type Props = {
    /** The outcome in words, or null while the job runs. */
    summary: string | null;
    /** Why the job failed, or null. Shown above the outcome, since it is what matters then. */
    failure: string | null;
    quarantined: number;
    /** The quarantine, once asked for. */
    items: QuarantinedItem[] | undefined;
    onShowQuarantine: () => void;
  };
  let { summary, failure, quarantined, items, onShowQuarantine }: Props = $props();
</script>

{#if summary}
  <div class="flex flex-col gap-1">
    {#if failure}
      <span class="text-xs text-destructive" title={failure}>{failure}</span>
    {/if}
    <span class="text-xs text-muted-foreground">{summary}</span>
    {#if quarantined > 0}
      {#if items}
        <ul class="flex flex-col gap-0.5 rounded bg-muted p-2">
          {#each items as item (item.item_id)}
            <!--
              On two lines: the panel is narrow, and side by side a reason of any length squeezed
              the identifier down to three characters — the one thing needed to find the item.
            -->
            <li class="flex flex-col text-xs">
              <span class="truncate font-mono" title={item.item_id}>{item.item_id}</span>
              {#if recordOf(item)}
                <span class="truncate text-muted-foreground" title={recordOf(item)}>
                  record {recordOf(item)}
                </span>
              {/if}
              <span class="text-muted-foreground">{item.reason}</span>
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
