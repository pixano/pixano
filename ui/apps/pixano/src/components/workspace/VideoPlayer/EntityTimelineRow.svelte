<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // One object of the timeline: a sticky header (cameras chevron, select, keyframe count or
  // camera coverage, edit pencil) and its lane. Pointer work on the lane (ticks,
  // scrubbing, dragging, the track menu) is delegated to the panel, which hit-tests the lane.
  import { CaretRight, Pencil } from "phosphor-svelte";

  import TimelineMissingCamera from "./TimelineMissingCamera.svelte";
  import TrackMarks from "./TrackMarks.svelte";
  import { entities } from "$lib/stores/workspaceStores.svelte";
  import { cameraRowsDomId } from "$lib/timeline/timelineCameras";
  import { TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";
  import { MARKS_ENTITY, type LaneGeom } from "$lib/timeline/types";
  import type { Entity } from "$lib/types/dataset";
  import { cn } from "$lib/utils/styleUtils";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";

  interface Props {
    entity: Entity;
    /** The lane drawn: every camera merged, or the camera shown alone. */
    lane: LaneGeom;
    /** "12 kf", "2/3 views", or "—" for an object a camera shown alone does not see. */
    meta: string;
    /** The row's block height, its 4 px gap included. */
    height: number;
    laneWidth: number;
    dotColor: string;
    selected: boolean;
    /** Opacity of the row's graphics: dimmed when hidden, out of a fusion, or not in the camera. */
    graphicsOpacity: number;
    marksVisible: boolean;
    /** Expanded into camera sub-rows: only a faint line, its ticks are on the sub-rows. */
    expanded?: boolean;
    /** A chevron to expand the row into cameras, a spacer to keep names aligned, or nothing. */
    leading?: "chevron" | "spacer" | null;
    onToggleExpanded?: () => void;
    /** The camera shown alone, when the object has no track in it. */
    missingView?: string | null;
    canAddInView?: boolean;
    addInViewUnavailableReason?: string | null;
    onAddInView?: () => void;
    editing: boolean;
    /** Why the pencil cannot edit on this frame, or null when it can. */
    editUnavailableReason: string | null;
    onSelect: () => void;
    onTogglePencil: () => void;
  }

  let {
    entity,
    lane,
    meta,
    height,
    laneWidth,
    dotColor,
    selected,
    graphicsOpacity,
    marksVisible,
    expanded = false,
    leading = null,
    onToggleExpanded,
    missingView = null,
    canAddInView = false,
    addInViewUnavailableReason = null,
    onAddInView,
    editing,
    editUnavailableReason,
    onSelect,
    onTogglePencil,
  }: Props = $props();

  // Committed changes update the entity in place, which Svelte does not see through the
  // prop: re-read its label on every commit of the entities. The row is named by its id,
  // as the object's inspector card is, so the two can be matched.
  const displayFeat = $derived.by(() => {
    void entities.value;
    return getDefaultDisplayFeat(entity);
  });
  const name = $derived(entity.id);
  const title = $derived(displayFeat ? `${displayFeat} (${entity.id})` : entity.id);
  const pencilTitle = $derived(
    editing ? "Finish editing (Enter)" : (editUnavailableReason ?? "Edit this object's box (E)"),
  );
</script>

<div class="flex" style:height="{height}px" data-timeline-slot={entity.id}>
  <div
    class="sticky left-0 z-20 shrink-0 bg-card pt-1"
    style:width="{TIMELINE_HEADER_WIDTH}px"
    data-timeline-header
  >
    <div
      class={cn(
        "group flex h-9 items-center gap-1.5 rounded-r-lg pr-1.5",
        leading ? "pl-1.5" : "pl-3",
        selected && "bg-timeline-row-selected",
      )}
    >
      {#if leading === "chevron"}
        <button
          type="button"
          class="grid size-6 shrink-0 place-items-center rounded-md text-foreground/65 transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          title={expanded ? "Hide the cameras" : "Show the cameras"}
          aria-label={`Cameras of ${name}`}
          aria-expanded={expanded}
          aria-controls={expanded ? cameraRowsDomId(entity.id) : undefined}
          onclick={onToggleExpanded}
        >
          <CaretRight
            weight="bold"
            class={cn(
              "size-3.5 transition-transform motion-reduce:transition-none",
              expanded && "rotate-90",
            )}
          />
        </button>
      {:else if leading === "spacer"}
        <span class="size-6 shrink-0" aria-hidden="true"></span>
      {/if}
      <button
        type="button"
        class="flex h-7 min-w-0 flex-1 items-center gap-2 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        {title}
        aria-pressed={selected}
        onclick={onSelect}
      >
        <span
          class="size-2.5 shrink-0 rounded-full"
          style:background={dotColor}
          style:opacity={graphicsOpacity}
        ></span>
        <span
          class={cn(
            "min-w-0 flex-1 truncate text-[13px] text-foreground",
            selected ? "font-semibold" : "font-medium",
          )}
        >
          {name}
        </span>
      </button>
      <span class="shrink-0 font-mono text-[11px] tabular-nums text-foreground/65">{meta}</span>
      <button
        type="button"
        class={cn(
          "size-6 shrink-0 place-items-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
          editing
            ? "grid bg-primary text-primary-foreground"
            : "hidden text-foreground/65 hover:bg-accent hover:text-foreground group-focus-within:grid group-hover:grid",
          selected && "grid",
          !editing && editUnavailableReason && "cursor-default opacity-50 hover:bg-transparent",
        )}
        title={pencilTitle}
        aria-label={editing ? `Finish editing ${name}` : `Edit ${name}`}
        aria-pressed={editing}
        aria-disabled={!editing && editUnavailableReason !== null}
        onclick={() => {
          if (editing || editUnavailableReason === null) onTogglePencil();
        }}
      >
        <Pencil class="size-3.5" />
      </button>
    </div>
  </div>
  <div
    class={cn(
      "relative isolate mt-1 h-9 shrink-0 rounded-md",
      selected && "bg-timeline-row-selected",
    )}
    style:width="{laneWidth}px"
    data-timeline-lane={entity.id}
  >
    <div class="absolute inset-0" style:opacity={graphicsOpacity}>
      <TrackMarks
        {lane}
        geo={MARKS_ENTITY}
        lineOpacity={expanded ? 0.25 : selected ? 0.9 : 0.5}
        showTicks={!expanded}
        visible={marksVisible}
      />
    </div>
    {#if missingView}
      <TimelineMissingCamera
        view={missingView}
        label={name}
        canAdd={canAddInView}
        addUnavailableReason={addInViewUnavailableReason}
        onAdd={() => onAddInView?.()}
      />
    {/if}
  </div>
</div>
