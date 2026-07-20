<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CheckCircle, CircleNotch, Prohibit, WarningCircle, X } from "phosphor-svelte";

  import { isTerminalJob, jobStateLabel, visibleJobEntries } from "./wizardUtils";
  import {
    dismissImportJob,
    importJobsStore,
    requestImportJobCancel,
  } from "$lib/stores/importJobsStore.svelte";

  const entries = $derived(visibleJobEntries(importJobsStore.value));
</script>

{#if entries.length}
  <div class="fixed bottom-4 right-4 z-40 flex w-80 flex-col gap-2">
    {#each entries as entry (entry.jobId)}
      {@const terminal = isTerminalJob(entry.job.status)}
      {@const done = entry.job.progress?.done ?? 0}
      {@const total = entry.job.progress?.total ?? null}
      {@const percent = total ? Math.min(100, Math.round((done / total) * 100)) : null}
      <div class="rounded-xl border border-border bg-card p-3 shadow-glass-lg">
        <div class="flex items-center gap-2">
          {#if entry.job.status === "done"}
            <CheckCircle weight="fill" class="h-4 w-4 shrink-0 text-primary" />
          {:else if entry.job.status === "cancelled"}
            <Prohibit weight="fill" class="h-4 w-4 shrink-0 text-muted-foreground" />
          {:else if terminal}
            <WarningCircle weight="fill" class="h-4 w-4 shrink-0 text-destructive" />
          {:else}
            <CircleNotch weight="regular" class="h-4 w-4 shrink-0 animate-spin text-primary" />
          {/if}
          <p class="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
            {entry.dataset || "Import"}
          </p>
          <span class="shrink-0 text-[10px] uppercase tracking-widest text-muted-foreground">
            {jobStateLabel(entry)}
          </span>
          {#if terminal}
            <button
              type="button"
              class="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
              aria-label="Dismiss"
              onclick={() => dismissImportJob(entry.jobId)}
            >
              <X weight="bold" class="h-3.5 w-3.5" />
            </button>
          {/if}
        </div>

        {#if !terminal}
          <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border">
            {#if percent !== null}
              <div
                class="h-full rounded-full bg-primary transition-[width] duration-500"
                style="width: {percent}%"
              ></div>
            {:else}
              <div class="h-full w-1/3 animate-pulse rounded-full bg-primary/60"></div>
            {/if}
          </div>
          <div class="mt-1.5 flex items-center justify-between">
            <span class="font-mono text-[10px] text-muted-foreground">
              {#if total}{done} / {total}{:else if done}{done} records{/if}
            </span>
            <button
              type="button"
              class="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-destructive disabled:opacity-50"
              disabled={entry.cancelRequested}
              onclick={() => void requestImportJobCancel(entry.jobId)}
            >
              Cancel
            </button>
          </div>
        {:else if entry.job.status === "error" || entry.job.status === "interrupted"}
          <p class="mt-1.5 line-clamp-2 text-xs text-destructive">
            {entry.job.error?.message || "The import stopped unexpectedly."}
          </p>
        {/if}
      </div>
    {/each}
  </div>
{/if}
