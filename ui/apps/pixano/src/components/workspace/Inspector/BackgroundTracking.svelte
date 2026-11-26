<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { FilmStrip, X } from "phosphor-svelte";

  import JobProgress from "../../jobs/JobProgress.svelte";
  import { isTerminal, type Job } from "$lib/api/jobsApi";
  import { canCancel, failureOf } from "$lib/stores/jobsStore.svelte";
  import {
    showTrackedLabel,
    TRACKING_OUTPUTS,
    trackingHint,
    trackingOutput,
    trackingSummary,
    type TrackingOutput,
  } from "$lib/tracking/backgroundTracking";

  type Props = {
    /** The job following the object; null before one is launched. */
    job: Job | null;
    /** The model a job would run; null when the inference serves none for tracking. */
    model: string | null;
    /** Why the object cannot be followed from this frame now; null when it can. */
    blocker: string | null;
    /** Whether the job is being submitted. */
    starting: boolean;
    /** Why the server refused the last job submitted; null when it did not. */
    refusal: string | null;
    /** Whether the workers' job lets one choose what it proposes. */
    choosable: boolean;
    /** What a job launched now would propose: masks, when the workers' job offers no choice. */
    output: TrackingOutput;
    /** What the job shown proposes. */
    jobOutput: TrackingOutput;
    /** Why what the job wrote cannot be shown now; or null. */
    showBlocker: string | null;
    onOutputChange: (output: TrackingOutput) => void;
    onTrack: () => void;
    onCancel: () => void;
    onShow: () => void;
    onDismiss: () => void;
  };
  let {
    job,
    model,
    blocker,
    starting,
    refusal,
    choosable,
    output,
    jobOutput,
    showBlocker,
    onOutputChange,
    onTrack,
    onCancel,
    onShow,
    onDismiss,
  }: Props = $props();
</script>

<div class="mt-2 flex flex-col gap-1.5 rounded-lg border border-border/60 bg-background/60 p-2">
  {#if job === null}
    <div class="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded border border-input px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
        disabled={blocker !== null || starting}
        title="Follow this object from this frame to the end of the video, in the background"
        onclick={onTrack}
      >
        <FilmStrip size={13} />
        {starting ? "Starting…" : "Track to the end"}
      </button>
      {#if choosable}
        <select
          aria-label="What the model proposes on each frame"
          class="rounded border border-input bg-background px-1.5 py-1 text-xs disabled:opacity-50"
          value={output}
          disabled={starting}
          onchange={(event) => onOutputChange(trackingOutput(event.currentTarget.value))}
        >
          {#each TRACKING_OUTPUTS as choice (choice.value)}
            <option value={choice.value}>{choice.label}</option>
          {/each}
        </select>
      {/if}
    </div>
    <p class="text-[11px] text-muted-foreground">
      {blocker ?? trackingHint(model, output)}
    </p>
    {#if refusal !== null}
      <p class="text-[11px] text-destructive">{refusal}</p>
    {/if}
  {:else}
    <div class="flex items-start justify-between gap-2">
      <span class="text-xs font-medium">{trackingSummary(job, jobOutput)}</span>
      {#if isTerminal(job.state)}
        <button
          type="button"
          aria-label="Dismiss"
          class="rounded p-0.5 text-muted-foreground hover:bg-muted"
          onclick={onDismiss}
        >
          <X size={12} />
        </button>
      {/if}
    </div>
    {#if !isTerminal(job.state)}
      <JobProgress {job} counted={false} />
      {#if canCancel(job)}
        <button
          type="button"
          class="self-start rounded border border-input px-2 py-0.5 text-xs hover:bg-muted"
          onclick={onCancel}
        >
          Cancel
        </button>
      {/if}
    {:else if job.state === "done" && job.produced > 0}
      <button
        type="button"
        class="self-start rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground disabled:opacity-50"
        disabled={showBlocker !== null}
        onclick={onShow}
      >
        {showTrackedLabel(jobOutput)}
      </button>
      {#if showBlocker !== null}
        <p class="text-[11px] text-muted-foreground">{showBlocker}</p>
      {/if}
    {:else if failureOf(job)}
      <p class="text-[11px] text-destructive">{failureOf(job)}</p>
    {/if}
  {/if}
</div>
