<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleNotch } from "phosphor-svelte";

  import type { IoJobResponse } from "$lib/api/restTypes";

  interface Props {
    job: IoJobResponse | null;
    cancelRequested: boolean;
  }

  let { job, cancelRequested }: Props = $props();

  const done = $derived(job?.progress?.done ?? 0);
  const total = $derived(job?.progress?.total ?? null);
  const percent = $derived(total ? Math.min(100, Math.round((done / total) * 100)) : null);
  const phaseLabel = $derived(
    cancelRequested
      ? "Cancelling (stops at the next commit)…"
      : (job?.progress?.phase ?? "starting"),
  );
  const tableCounts = $derived(Object.entries(job?.progress?.table_counts ?? {}));
</script>

<div class="px-6 sm:px-7 pb-2 space-y-4">
  <div class="flex items-center gap-2 text-sm text-foreground">
    <CircleNotch weight="regular" class="h-4 w-4 animate-spin text-primary" />
    <span class="capitalize">{phaseLabel}</span>
    {#if percent !== null}
      <span class="ml-auto font-mono text-xs text-muted-foreground">
        {done} / {total} · {percent}%
      </span>
    {:else if done}
      <span class="ml-auto font-mono text-xs text-muted-foreground">{done} records</span>
    {/if}
  </div>

  <div class="h-2 w-full overflow-hidden rounded-full bg-border">
    {#if percent !== null}
      <div
        class="h-full rounded-full bg-primary transition-[width] duration-500"
        style="width: {percent}%"
      ></div>
    {:else}
      <div class="h-full w-1/3 animate-pulse rounded-full bg-primary/60"></div>
    {/if}
  </div>

  {#if tableCounts.length}
    <div class="flex flex-wrap gap-1.5">
      {#each tableCounts as [table, count] (table)}
        <span
          class="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
        >
          {table}: {count}
        </span>
      {/each}
    </div>
  {/if}

  <p class="text-xs text-muted-foreground">
    The import runs on the server as job
    <span class="font-mono">{job?.job_id ?? "…"}</span>
    — it keeps running if you close this window, and an interrupted job can be resumed later.
  </p>
</div>
