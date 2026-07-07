<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CheckCircle, Prohibit, WarningCircle } from "phosphor-svelte";

  import type { IoJobResponse } from "$lib/api/restTypes";

  interface Props {
    job: IoJobResponse | null;
    errorMessage: string;
  }

  let { job, errorMessage }: Props = $props();

  const cancelled = $derived(job?.status === "cancelled");
  const tableCounts = $derived(Object.entries(job?.progress?.table_counts ?? {}));
</script>

<div class="px-6 sm:px-7 pb-2 space-y-3">
  {#if errorMessage}
    <div class="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
      <p class="flex items-center gap-2 text-sm font-medium text-destructive">
        <WarningCircle weight="fill" class="h-4 w-4 shrink-0" />
        Import failed
      </p>
      <p class="mt-1 whitespace-pre-wrap text-xs text-foreground/80">{errorMessage}</p>
    </div>
  {:else if cancelled}
    <div class="rounded-xl border border-border bg-card p-4">
      <p class="flex items-center gap-2 text-sm font-medium text-foreground">
        <Prohibit weight="fill" class="h-4 w-4 shrink-0 text-muted-foreground" />
        Import cancelled
      </p>
      <p class="mt-1 text-xs text-muted-foreground">Nothing was promoted to your library.</p>
    </div>
  {:else}
    <div class="rounded-xl border border-primary/30 bg-primary/5 p-4">
      <p class="flex items-center gap-2 text-sm font-medium text-foreground">
        <CheckCircle weight="fill" class="h-4 w-4 shrink-0 text-primary" />
        Dataset imported
      </p>
      {#if tableCounts.length}
        <div class="mt-2 flex flex-wrap gap-1.5">
          {#each tableCounts as [table, count] (table)}
            <span
              class="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
            >
              {table}: {count}
            </span>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
