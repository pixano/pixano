<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Job } from "$lib/api/jobsApi";
  import { progressOf } from "$lib/stores/jobsStore.svelte";

  type Props = { job: Job };
  let { job }: Props = $props();

  const ratio = $derived(progressOf(job));
  const percent = $derived(Math.round(ratio * 100));
  // Planning has no denominator yet — the worker is still deciding how much work there is.
  const indeterminate = $derived(job.state === "planning");
</script>

<div class="flex flex-col gap-1">
  <div
    class="h-1.5 w-full overflow-hidden rounded bg-muted"
    role="progressbar"
    aria-valuenow={indeterminate ? undefined : percent}
    aria-valuemin={0}
    aria-valuemax={100}
    aria-label="Job progress"
  >
    <div
      class="h-full rounded transition-[width] duration-300"
      class:bg-primary={job.state !== "error"}
      class:bg-destructive={job.state === "error"}
      style:width={indeterminate ? "100%" : `${percent}%`}
      class:animate-pulse={indeterminate}
    ></div>
  </div>
  <span class="text-xs text-muted-foreground">
    {#if indeterminate}
      Planning…
    {:else}
      {job.done_tasks} / {job.total_tasks} tasks
    {/if}
  </span>
</div>
