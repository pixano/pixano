<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // One object of the timeline: a sticky header (select, keyframe count, edit pencil, pin)
  // and its lane. Pointer work on the lane (ticks, scrubbing, dragging, the track menu) is
  // delegated to the panel, which hit-tests the lane's model.
  import { Pencil, PushPin } from "phosphor-svelte";

  import TrackMarks from "./TrackMarks.svelte";
  import { entities } from "$lib/stores/workspaceStores.svelte";
  import { TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";
  import { rowKeyframeLabel } from "$lib/timeline/timelineRows";
  import { MARKS_ENTITY, type EntityTrackModel } from "$lib/timeline/types";
  import type { Entity } from "$lib/types/dataset";
  import { cn } from "$lib/utils/styleUtils";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";

  interface Props {
    entity: Entity;
    model: EntityTrackModel;
    /** The row's block height, its 4 px gap included. */
    height: number;
    laneWidth: number;
    dotColor: string;
    selected: boolean;
    pinned: boolean;
    /** Opacity of the row's graphics: dimmed when hidden in the inspector or out of a fusion. */
    graphicsOpacity: number;
    marksVisible: boolean;
    editing: boolean;
    /** Why the pencil cannot edit on this frame, or null when it can. */
    editUnavailableReason: string | null;
    onSelect: () => void;
    onTogglePin: () => void;
    onTogglePencil: () => void;
  }

  let {
    entity,
    model,
    height,
    laneWidth,
    dotColor,
    selected,
    pinned,
    graphicsOpacity,
    marksVisible,
    editing,
    editUnavailableReason,
    onSelect,
    onTogglePin,
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
  const keyframeLabel = $derived(rowKeyframeLabel(model.union.frames.length));
  const pencilTitle = $derived(
    editing ? "Finish editing (Enter)" : (editUnavailableReason ?? "Edit this object's box (E)"),
  );
</script>

<div class="flex" style:height="{height}px" data-timeline-row={entity.id}>
  <div
    class="sticky left-0 z-20 shrink-0 bg-card pt-1"
    style:width="{TIMELINE_HEADER_WIDTH}px"
    data-timeline-header
  >
    <div
      class={cn(
        "group flex h-9 items-center gap-1.5 rounded-r-lg pl-3 pr-1.5",
        selected && "bg-timeline-row-selected",
      )}
    >
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
      <span class="shrink-0 font-mono text-[11px] tabular-nums text-foreground/65">
        {keyframeLabel}
      </span>
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
      <button
        type="button"
        class={cn(
          "grid size-6 shrink-0 place-items-center rounded-md transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
          pinned ? "text-foreground" : "text-foreground/50 hover:text-foreground",
        )}
        title={pinned ? "Unpin" : "Pin to the top"}
        aria-label={`Pin ${name}`}
        aria-pressed={pinned}
        onclick={onTogglePin}
      >
        <PushPin weight={pinned ? "fill" : "regular"} class="size-[15px]" />
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
        lane={model.union}
        geo={MARKS_ENTITY}
        lineOpacity={selected ? 0.9 : 0.5}
        visible={marksVisible}
      />
    </div>
  </div>
</div>
