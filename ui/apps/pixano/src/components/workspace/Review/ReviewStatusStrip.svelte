<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, X } from "phosphor-svelte";

  import { formatConfidence } from "$lib/constants/annotationTypeMeta";
  import { REVIEW_STATUS } from "$lib/constants/reviewConstants";
  import type { ReviewSummary } from "$lib/utils/reviewStatus";
  import { cn } from "$lib/utils/styleUtils";

  // Where a model's proposal stands with its reviewer: a chip with the model and its score, and,
  // while it is still to review, Accept and Reject.

  interface Props {
    summary: ReviewSummary;
    /** What the decision covers: an object, as it shows, or one annotation. */
    scope: "object" | "annotation";
    /** Whether Accept and Reject are offered while it is still to review. */
    canDecide: boolean;
    onAccept: () => void;
    onReject: () => void;
  }

  let { summary, scope, canDecide, onAccept, onReject }: Props = $props();

  const TITLES = {
    object: {
      accept: "Accept what the model proposed for this object, as shown; saved with your changes",
      reject:
        "Reject what the model proposed for this object, as shown: it is deleted, and the object once nothing else is left on it; saved with your changes",
    },
    annotation: {
      accept: "Accept this annotation as the model proposed it; saved with your changes",
      reject: "Reject this annotation: it is deleted; saved with your changes",
    },
  } as const;

  const isPending = $derived(summary.status === REVIEW_STATUS.PENDING);
  const label = $derived.by(() => {
    if (isPending) {
      return summary.pendingCount > 1
        ? `Pending review · ${summary.pendingCount}`
        : "Pending review";
    }
    return summary.unsaved ? "Accepted, not saved" : "Accepted";
  });
</script>

<div class="flex items-center justify-between gap-1.5 min-w-0">
  <div class="flex items-center gap-1.5 min-w-0">
    <span
      class={cn(
        "flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium leading-none",
        isPending
          ? "bg-warning/10 text-warning border-warning/20"
          : "bg-success/10 text-success border-success/20",
      )}
    >
      {label}
    </span>
    {#if summary.model}
      <span class="text-[10px] text-muted-foreground truncate" title="The model that proposed it">
        {summary.model}
      </span>
    {/if}
    {#if summary.score !== null}
      <span
        class="flex-shrink-0 text-[10px] font-mono text-muted-foreground"
        title="The model's confidence"
      >
        {formatConfidence(summary.score)}
      </span>
    {/if}
    {#if isPending && summary.hiddenCount > 0}
      <span
        class="flex-shrink-0 text-[10px] text-muted-foreground"
        title="Hidden, by its eye or a filter: it stays to review"
      >
        · {summary.hiddenCount} hidden
      </span>
    {/if}
  </div>
  {#if isPending && canDecide}
    <div class="flex-shrink-0 flex items-center gap-1">
      <button
        type="button"
        class="inline-flex items-center gap-1 h-6 px-2 rounded-md border border-success/30 bg-success/10 text-[11px] font-medium text-success transition-colors hover:bg-success/20"
        title={TITLES[scope].accept}
        onclick={onAccept}
      >
        <Check weight="bold" class="h-3 w-3" />
        Accept
      </button>
      <button
        type="button"
        class="inline-flex items-center gap-1 h-6 px-2 rounded-md border border-destructive/30 bg-destructive/10 text-[11px] font-medium text-destructive transition-colors hover:bg-destructive/20"
        title={TITLES[scope].reject}
        onclick={onReject}
      >
        <X weight="bold" class="h-3 w-3" />
        Reject
      </button>
    </div>
  {/if}
</div>
