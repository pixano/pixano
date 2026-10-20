<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // One camera of an expanded object row: the camera's keyframes, or what is missing there.
  // Clicking it makes that camera the active one, which the keyframe tools and the pencil
  // follow.
  import { VideoCamera } from "phosphor-svelte";

  import TimelineMissingCamera from "./TimelineMissingCamera.svelte";
  import TrackMarks from "./TrackMarks.svelte";
  import { TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";
  import { rowKeyframeLabel } from "$lib/timeline/timelineRows";
  import { MARKS_VIEW, type LaneGeom } from "$lib/timeline/types";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    /** The row's layout key, which the panel reads back from the DOM. */
    slotKey: string;
    /** The object's id, for labels. */
    entityId: string;
    view: string;
    /** The camera's lane, or null when the object has no track in it. */
    lane: LaneGeom | null;
    /** The block height, its 4 px gap included. */
    height: number;
    laneWidth: number;
    /** The active camera: its dot shows on every expanded object. */
    active: boolean;
    /** The active camera of the selected object: its sub-row is highlighted too. */
    highlighted: boolean;
    graphicsOpacity: number;
    marksVisible: boolean;
    canAddInView: boolean;
    addInViewUnavailableReason: string | null;
    onActivate: () => void;
    onAddInView: () => void;
  }

  let {
    slotKey,
    entityId,
    view,
    lane,
    height,
    laneWidth,
    active,
    highlighted,
    graphicsOpacity,
    marksVisible,
    canAddInView,
    addInViewUnavailableReason,
    onActivate,
    onAddInView,
  }: Props = $props();

  const meta = $derived(lane ? rowKeyframeLabel(lane.frames.length) : "—");
</script>

<div
  class="flex"
  style:height="{height}px"
  data-timeline-slot={slotKey}
  data-timeline-object={entityId}
  data-timeline-view={view}
>
  <div
    class="sticky left-0 z-20 shrink-0 bg-card pt-1"
    style:width="{TIMELINE_HEADER_WIDTH}px"
    data-timeline-header
  >
    <button
      type="button"
      class={cn(
        "flex h-7 w-full items-center gap-2 rounded-r-lg pl-[52px] pr-9 text-left transition-colors hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        highlighted && "bg-timeline-row-active-view",
      )}
      title={lane ? `${entityId} in ${view}` : `${entityId} is not annotated in ${view}`}
      aria-current={highlighted ? "true" : undefined}
      aria-label={`${view}${active ? ", active camera" : ""}, ${lane ? `${lane.frames.length} keyframes` : "not annotated"}`}
      onclick={onActivate}
    >
      <VideoCamera class="size-3.5 shrink-0 text-foreground/65" />
      <span class="min-w-0 flex-1 truncate text-xs text-foreground">{view}</span>
      {#if active}
        <span class="size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true"></span>
      {/if}
      <span class="shrink-0 font-mono text-[11px] tabular-nums text-foreground/65">{meta}</span>
    </button>
  </div>
  <div
    class={cn(
      "relative isolate mt-1 h-7 shrink-0 rounded-md",
      highlighted && "bg-timeline-row-active-view",
    )}
    style:width="{laneWidth}px"
    data-timeline-lane={slotKey}
  >
    {#if lane}
      <div class="absolute inset-0" style:opacity={graphicsOpacity}>
        <TrackMarks {lane} geo={MARKS_VIEW} lineOpacity={0.7} visible={marksVisible} />
      </div>
    {:else}
      <TimelineMissingCamera
        {view}
        label={entityId}
        canAdd={canAddInView}
        addUnavailableReason={addInViewUnavailableReason}
        onAdd={onAddInView}
      />
    {/if}
  </div>
</div>
