<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts" module>
  // How the focus last moved: Tab moves it on purpose, a click may leave it on a control by chance.
  // Kept for the page, not for one mount: the inspector remounts this component as it reloads.
  let focusMovedByTab = false;
</script>

<script lang="ts">
  import { tick, untrack } from "svelte";

  import { isInOverlay } from "../canvas2d/boxInteraction";
  import ReviewNextPrompt from "./ReviewNextPrompt.svelte";
  import { saveAndOpenNextRecord } from "$lib/stores/reviewNavigationStore.svelte";
  import {
    annotations,
    editedTrackletId,
    highlightedEntity,
    itemMetas,
    newShape,
    reviewedAnnotation,
    reviewStartedOnRecord,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { ToolType } from "$lib/tools";
  import type { Entity } from "$lib/types/dataset";
  import { canTakeReviewDecision } from "$lib/utils/reviewActions";
  import {
    clearAnnotationUnderReview,
    followReview,
    promptAnswerOfKey,
    reviewDecisionOfKey,
    reviewFirstAnnotation,
    reviewKeyIsFree,
    takeReviewKey,
    type ReviewKeyDecision,
    type ReviewTarget,
  } from "$lib/utils/reviewKeyboard";
  import { pendingReviewOf } from "$lib/utils/reviewStatus";

  // The review's keys, mounted while the review mode is on: Enter accepts the annotation under
  // review, Delete rejects it, and once nothing is left for them, Enter asks to save and go to the
  // next record. The rules are `reviewKeyboard.ts`'s; this component keeps the annotation under
  // review with the record, the focus and what is left to review, reads the page's focus for the
  // keys, and holds the prompt.

  interface Props {
    /** The objects the inspector lists, in its order. */
    objects: Entity[];
  }

  let { objects }: Props = $props();

  const TAB_KEY = "Tab";
  // The controls Enter presses. The workspace's container takes the focus too, and presses nothing.
  const PRESSABLE_CONTROLS =
    'button, a[href], summary, [role="button"], [role="switch"], [role="checkbox"], [role="menuitem"], [role="option"], [role="radio"]';

  let promptIsOpen = $state(false);
  const pendingLeft = $derived(pendingReviewOf(annotations.value).length);
  // What was left to review when the annotation under review was last checked.
  let leftToReview: ReviewTarget[] = [];

  const isPanTool = (): boolean => (selectedTool.value?.type ?? ToolType.Pan) === ToolType.Pan;

  // A record opened in review, or the review turned on, brings its first annotation to review under
  // review — the focused entity's, if any —, once a record: the keys then act on a visible target
  // from the first press. It waits for the Pan tool, the only one a focus holds under, and for the
  // inspector to apply what it hides, as the confidence filter.
  $effect(() => {
    const recordId = itemMetas.value?.item.id ?? null;
    if (recordId === null || recordId === reviewStartedOnRecord.value || !isPanTool()) return;
    untrack(() => {
      reviewStartedOnRecord.value = recordId;
      void tick().then(() => {
        if (isPanTool()) reviewFirstAnnotation(objects);
      });
    });
  });

  // A prompt belongs to the record it was opened on.
  $effect(() => {
    void itemMetas.value?.item.id;
    untrack(() => (promptIsOpen = false));
  });

  // The annotation under review follows what is left to review — one decided with the mouse,
  // deleted or hidden gives way to the next — and the focus: a click on another entity reviews it.
  $effect(() => {
    void annotations.value;
    void reviewedAnnotation.value;
    void highlightedEntity.value;
    const listed = objects;
    untrack(() => {
      leftToReview = followReview(leftToReview, listed);
    });
  });

  // Out of review, no annotation is under review.
  $effect(() => () => clearAnnotationUnderReview());

  function isTyping(): boolean {
    const active = document.activeElement;
    return (
      active instanceof HTMLInputElement ||
      active instanceof HTMLTextAreaElement ||
      active instanceof HTMLSelectElement ||
      (active instanceof HTMLElement && active.isContentEditable)
    );
  }

  /** A control a keyboard user reached with Tab, not one a click left the focus on. */
  function controlHasKeyboardFocus(): boolean {
    const active = document.activeElement;
    return focusMovedByTab && active instanceof HTMLElement && active.matches(PRESSABLE_CONTROLS);
  }

  function isFreeFor(decision: ReviewKeyDecision, event: KeyboardEvent): boolean {
    return (
      canTakeReviewDecision() &&
      reviewKeyIsFree(decision, {
        toolType: selectedTool.value?.type ?? ToolType.Pan,
        shape: newShape.value,
        isEditing:
          editedTrackletId.value !== null ||
          annotations.value.some((annotation) => annotation.ui.displayControl.editing),
        isTyping: isTyping(),
        inOverlay: isInOverlay(event.target as Element | null),
        controlHasKeyboardFocus: controlHasKeyboardFocus(),
      })
    );
  }

  function answerPrompt(event: KeyboardEvent): void {
    const answer = promptAnswerOfKey(event);
    if (answer === "none") return;
    promptIsOpen = false;
    if (answer === "go" && isFreeFor("accept", event)) {
      event.preventDefault();
      void saveAndOpenNextRecord();
    }
  }

  function handleKeyDown(event: KeyboardEvent): void {
    if (event.key === TAB_KEY) focusMovedByTab = true;
    if (promptIsOpen) {
      answerPrompt(event);
      return;
    }
    const decision = reviewDecisionOfKey(event);
    if (decision === null || !isFreeFor(decision, event)) return;
    const outcome = takeReviewKey(decision, objects, highlightedEntity.value);
    if (outcome === "nothing" && decision === "accept") promptIsOpen = true;
    // The key acted: a button a click left the focus on is not pressed by it too.
    if (outcome !== "nothing" || promptIsOpen) event.preventDefault();
  }

  function handlePointerDown(): void {
    focusMovedByTab = false;
    promptIsOpen = false;
  }
</script>

<svelte:window onkeydown={handleKeyDown} onpointerdown={handlePointerDown} />

{#if promptIsOpen}
  <ReviewNextPrompt {pendingLeft} />
{/if}
