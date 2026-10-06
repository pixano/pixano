<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onDestroy, onMount } from "svelte";

  import JobOutcome from "./JobOutcome.svelte";
  import JobProgress from "./JobProgress.svelte";
  import SubmitJobForm from "./SubmitJobForm.svelte";
  import type { JobTarget } from "$lib/api/jobsApi";
  import {
    canCancel,
    failureOf,
    jobsStore,
    outcomeOf,
    stateLabelOf,
  } from "$lib/stores/jobsStore.svelte";

  type Props = { dataset: JobTarget | null };
  let { dataset }: Props = $props();

  onMount(() => {
    void jobsStore.start();
  });
  onDestroy(() => jobsStore.stop());

  async function run(kind: string, params: Record<string, unknown>): Promise<boolean> {
    if (!dataset) return false;
    return jobsStore.submit(kind, dataset.id, params);
  }
</script>

<div class="flex h-full min-h-0 flex-col overflow-hidden">
  {#if jobsStore.runnable}
    <!--
      The form scrolls on its own, within a share of the panel: a kind with many parameters
      would push the Run button out of sight and leave the job list no room at all.
    -->
    <div class="max-h-[60%] shrink-0 overflow-y-auto border-b border-border">
      <SubmitJobForm
        kinds={jobsStore.kinds}
        {dataset}
        servedModels={jobsStore.servedModels}
        onSubmit={run}
      />
    </div>
  {:else if !jobsStore.loading}
    <p class="border-b border-border p-3 text-xs text-muted-foreground">
      No worker is running, so nothing can be launched. Start pixano-worker and reopen this panel.
    </p>
  {/if}

  {#if jobsStore.error}
    <p class="border-b border-border bg-destructive/10 p-3 text-xs text-destructive">
      {jobsStore.error}
    </p>
  {/if}

  <div class="min-h-0 flex-1 overflow-y-auto">
    {#if jobsStore.loading}
      <p class="p-3 text-xs text-muted-foreground">Loading…</p>
    {:else if jobsStore.jobs.length === 0}
      <p class="p-3 text-xs text-muted-foreground">No job has been run yet.</p>
    {:else}
      <ul class="flex flex-col">
        {#each jobsStore.jobs as job (job.id)}
          <li class="flex flex-col gap-2 border-b border-border p-3">
            <div class="flex items-baseline justify-between gap-2">
              <span class="truncate text-sm font-medium">{job.kind}</span>
              <span class="shrink-0 text-xs text-muted-foreground">{stateLabelOf(job)}</span>
            </div>
            <JobProgress {job} />
            <JobOutcome
              summary={outcomeOf(job)}
              failure={failureOf(job)}
              quarantined={job.quarantined}
              items={jobsStore.quarantines[job.id]}
              onShowQuarantine={() => jobsStore.loadQuarantine(job.id)}
            />
            {#if canCancel(job)}
              <button
                type="button"
                class="self-start rounded border border-input px-2 py-1 text-xs hover:bg-muted"
                onclick={() => jobsStore.cancel(job.id)}
              >
                Cancel
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  {#if !jobsStore.live && !jobsStore.loading}
    <!--
      Worth saying, because the numbers on screen stop moving without any other sign. The
      stream retries on its own, so this is a passing state, not an error to act on.
    -->
    <p class="border-t border-border p-2 text-xs text-muted-foreground">
      Reconnecting to the event stream…
    </p>
  {/if}
</div>
