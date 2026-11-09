<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, ChevronsRight, Loader2, RotateCcw, Save, X } from "lucide-svelte";

  import {
    HUMAN_REVIEW_FILTER,
    REVIEW_STATUS,
    type ReviewFilterKey,
  } from "$lib/annotations/reviewStatus.js";
  // Measured here, next to the grid, so the controller stays environment-agnostic
  // — the same split `LeftPanel` uses when it opens a record.
  import { measureGridViewport } from "$lib/workspace/layoutPlanner.js";
  import type {
    AcceptRefusal,
    RejectRefusal,
    ReviewController,
    ReviewRow,
  } from "$lib/workspace/reviewController.svelte.js";

  interface Props {
    review: ReviewController;
    saving: boolean;
    saveError: string | null;
  }

  let { review, saving, saveError }: Props = $props();

  /** How many digits of a model's score the list shows. */
  const CONFIDENCE_DIGITS = 2;

  // What each chip says and how its badge looks — written here, where it shows.
  const CHIPS: readonly { key: ReviewFilterKey; label: string; badgeClass: string }[] = [
    {
      key: REVIEW_STATUS.PENDING,
      label: "Pending",
      badgeClass: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
    },
    {
      key: REVIEW_STATUS.ACCEPTED,
      label: "Accepted",
      badgeClass: "bg-green-500/15 text-green-700 dark:text-green-300",
    },
    { key: HUMAN_REVIEW_FILTER, label: "Human", badgeClass: "bg-muted text-muted-foreground" },
  ];

  /** The statuses "Save & next" can look for: every chip but the human one. */
  const NEXT_STATUS_CHIPS = CHIPS.filter((chip) => chip.key !== HUMAN_REVIEW_FILTER);

  function chipOf(key: ReviewFilterKey) {
    return CHIPS.find((chip) => chip.key === key) ?? CHIPS[CHIPS.length - 1];
  }

  function statusWord(key: ReviewFilterKey): string {
    return chipOf(key).label.toLowerCase();
  }

  /** How a row's controls name its annotation, so each button says which one it acts on. */
  function annotationName(row: ReviewRow): string {
    return `${row.label || "No label"} (${row.kind})`;
  }

  /** Why "Save & next" holds a decision back. */
  const BUSY_REASON = "Not while Save & next is running";

  /** Each reason the controller gives for not offering a decision, in words. */
  const ACCEPT_REFUSALS: Record<AcceptRefusal, string> = {
    accepted: "Already accepted",
    busy: BUSY_REASON,
  };
  const REJECT_REFUSALS: Record<RejectRefusal, string> = { busy: BUSY_REASON };
</script>

<div class="flex flex-col gap-3 p-3">
  <!-- Unsaved work on the whole record — decisions, edits, drafts, work a tool holds
       — counted as every widget toolbar counts it, and its Save. -->
  <div class="flex items-center justify-between gap-2">
    <p class="text-xs text-muted-foreground">
      {review.unsavedCount} unsaved
    </p>
    <div class="flex items-center gap-1">
      <!-- Undoes the decisions taken here too: the record goes back as it was last
           saved, work a tool holds included. -->
      <button
        type="button"
        onclick={() => review.discard()}
        disabled={!review.canDiscard || saving}
        title="Discard every unsaved change of this record"
        class="flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[11px]
          text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed
          disabled:opacity-40"
      >
        <RotateCcw class="h-3 w-3" />
        Discard
      </button>
      <button
        type="button"
        onclick={() => review.save()}
        disabled={!review.canSave || saving}
        title="Save every change of this record"
        class="flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[11px]
          text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed
          disabled:opacity-40"
      >
        {#if saving}
          <Loader2 class="h-3 w-3 animate-spin" />
        {:else}
          <Save class="h-3 w-3" />
        {/if}
        Save
      </button>
    </div>
  </div>
  {#if saveError}
    <p class="text-[11px] text-destructive">{saveError}</p>
  {/if}

  <!-- Status chips: each one shows or hides its annotations, here and on every canvas. -->
  <div class="flex flex-wrap gap-1" role="group" aria-label="Filter by review status">
    {#each CHIPS as chip (chip.key)}
      {@const shown = !review.isHidden(chip.key)}
      <button
        type="button"
        aria-pressed={shown}
        onclick={() => review.toggle(chip.key)}
        title={shown
          ? `Hide ${chip.label.toLowerCase()} annotations`
          : `Show ${chip.label.toLowerCase()} annotations`}
        class="flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition-colors
          {shown
          ? 'border-primary bg-primary/10 text-foreground'
          : 'border-border text-muted-foreground line-through hover:bg-accent/40'}"
      >
        {chip.label}
        <span class="tabular-nums text-muted-foreground">{review.counts[chip.key]}</span>
      </button>
    {/each}
  </div>

  {#if review.rows.length === 0}
    <p class="text-xs text-muted-foreground">No annotation to show with these filters.</p>
  {:else}
    <ul class="space-y-1" aria-label="Annotations of this record">
      {#each review.rows as row (row.id)}
        {@const chip = chipOf(row.filterKey)}
        <li
          class="flex items-center gap-1.5 rounded-md border px-2 py-1.5 {row.selected
            ? 'border-primary bg-primary/10'
            : 'border-border bg-card'}"
        >
          <!-- Named by its content; the selection, shown by colour, is told to assistive tech too. -->
          <button
            type="button"
            onclick={() => review.select(row.id)}
            aria-current={row.selected ? "true" : undefined}
            title="Select this annotation"
            class="flex min-w-0 flex-1 flex-col items-start text-left"
          >
            <span class="flex w-full min-w-0 items-center gap-1.5">
              <span class="truncate text-xs font-medium text-card-foreground">
                {row.label || "No label"}
              </span>
              <span class="shrink-0 rounded bg-muted px-1 text-[10px] text-muted-foreground">
                {row.kind}
              </span>
            </span>
            <span class="w-full truncate text-[10px] text-muted-foreground">
              {#if row.filterKey === HUMAN_REVIEW_FILTER}
                {row.persisted ? "Made by a person" : "Unsaved draft"}
              {:else}
                {row.source || "Unknown model"}{row.modelVersion ? ` ${row.modelVersion}` : ""}
                {#if row.confidence !== undefined}
                  · {row.confidence.toFixed(CONFIDENCE_DIGITS)}
                {/if}
              {/if}
            </span>
          </button>
          <span class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium {chip.badgeClass}">
            {chip.label}
          </span>
          {#if row.filterKey !== HUMAN_REVIEW_FILTER}
            <!-- Each button names the annotation it decides on: a list read aloud is
                 otherwise a run of identical "Accept"s. A refused one says why, in
                 its tooltip and in its description. -->
            {@const acceptReasonId = `review-accept-reason-${row.id}`}
            {@const rejectReasonId = `review-reject-reason-${row.id}`}
            {@const acceptRefusal = row.acceptRefusal ? ACCEPT_REFUSALS[row.acceptRefusal] : null}
            {@const rejectRefusal = row.rejectRefusal ? REJECT_REFUSALS[row.rejectRefusal] : null}
            <button
              type="button"
              onclick={() => review.accept(row.id)}
              disabled={!row.canAccept}
              title={acceptRefusal ?? "Accept"}
              aria-label={`Accept ${annotationName(row)}`}
              aria-describedby={acceptRefusal ? acceptReasonId : undefined}
              class="shrink-0 rounded p-1 text-muted-foreground hover:bg-green-500/15
                hover:text-green-700 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <Check class="h-3.5 w-3.5" />
            </button>
            {#if acceptRefusal}
              <span id={acceptReasonId} class="sr-only">{acceptRefusal}</span>
            {/if}
            <!-- Reject deletes the row. -->
            <button
              type="button"
              onclick={() => review.reject(row.id)}
              disabled={!row.canReject}
              title={rejectRefusal ?? "Reject: delete this annotation"}
              aria-label={`Reject ${annotationName(row)}`}
              aria-describedby={rejectRefusal ? rejectReasonId : undefined}
              class="shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/15
                hover:text-destructive disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <X class="h-3.5 w-3.5" />
            </button>
            {#if rejectRefusal}
              <span id={rejectReasonId} class="sr-only">{rejectRefusal}</span>
            {/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  <!-- Save, then open the next record holding annotations of the chosen status. -->
  <div class="flex flex-col gap-1.5 border-t border-border pt-3">
    <label class="flex items-center gap-1.5 text-[11px] text-muted-foreground">
      Next record with
      <select
        value={review.nextStatus}
        onchange={(e) => review.setNextStatus(e.currentTarget.value)}
        class="rounded-md border border-input bg-background px-1.5 py-0.5 text-[11px] text-foreground"
      >
        {#each NEXT_STATUS_CHIPS as chip (chip.key)}
          <option value={chip.key}>{chip.label.toLowerCase()}</option>
        {/each}
      </select>
      annotations
    </label>
    <button
      type="button"
      onclick={() => review.saveAndNext(measureGridViewport())}
      disabled={review.navigating || saving}
      title="Save this record, then open the next one holding annotations of the chosen status"
      class="flex items-center justify-center gap-1 rounded-md bg-primary px-2 py-1 text-xs
        font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed
        disabled:opacity-50"
    >
      {#if review.navigating}
        <Loader2 class="h-3.5 w-3.5 animate-spin" />
      {:else}
        <ChevronsRight class="h-3.5 w-3.5" />
      {/if}
      Save & next
    </button>
    <!--
      The server counts only the annotations a widget here can show: a model's rows on a video's
      frames, which no interface reviews yet, are not among them.
    -->
    {#if review.outcome?.kind === "opened"}
      <p class="text-[11px] text-muted-foreground">
        {review.outcome.remaining}
        {review.outcome.remaining === 1 ? "record holds" : "records hold"}
        {statusWord(review.outcome.status)} annotations to review here, this one included.
      </p>
    {:else if review.outcome?.kind === "none-left"}
      <p class="text-[11px] text-muted-foreground">
        No other record has {statusWord(review.outcome.status)} annotations to review here.
      </p>
    {:else if review.outcome?.kind === "not-saved"}
      <p class="text-[11px] text-destructive">
        {review.outcome.saveFailed
          ? "Not moved: the save failed."
          : "Not moved: some work is still unsaved — finish or discard it first."}
      </p>
    {:else if review.outcome?.kind === "failed"}
      <p class="text-[11px] text-destructive">
        Could not move to the next record: {review.outcome.message}
      </p>
    {/if}
  </div>
</div>
