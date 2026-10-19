<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Pencil, PushPin, PushPinSlash } from "phosphor-svelte";

  import TrackletSegment from "./TrackletSegment.svelte";
  import { shapeTopEntityId } from "$lib/stores/trackEditing";
  import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
  import {
    annotationColors,
    annotations,
    current_itemBBoxes,
    current_itemKeypoints,
    entities,
    highlightedEntity,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { ToolType } from "$lib/tools";
  import type { TrackTimelineEntry, View } from "$lib/ui";
  import {
    BaseSchema,
    cn,
    ContextMenu,
    Entity,
    IconButton,
    Tooltip,
    TooltipContent,
    Tracklet,
  } from "$lib/ui";
  import {
    editModeBlockedReason,
    editTrack,
    isEntityEditing,
    toggleEditModeForEntity,
  } from "$lib/utils/editMode";
  import { deleteEntity } from "$lib/utils/entityDeletion";
  import { highlightEntity } from "$lib/utils/highlightOperations";
  import { passiveTriggerProps } from "$lib/utils/tooltipTriggerProps";
  import {
    addKeyItemToTracklet,
    findNeighborFrameIndices,
    splitTrackletAfter,
  } from "$lib/utils/trackletOperations";
  import { updateView } from "$lib/utils/videoOperations";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";

  type MView = Record<string, View | View[]>;

  interface Props {
    entity: Entity;
    views: MView;
    onFrameClick: (imageIndex: number) => void;
    resetTool: () => void;
    isPinned?: boolean;
    isPrimaryFocus?: boolean;
    onTogglePin?: () => void;
  }

  let {
    entity,
    views,
    onFrameClick,
    resetTool,
    isPinned = false,
    isPrimaryFocus = false,
    onTogglePin,
  }: Props = $props();

  let objectTimeTrack: HTMLElement = $state();
  // The entity and its tracklets are updated in place by committed changes, which
  // Svelte does not see through the prop: re-read them on every commit of their store.
  let displayName: string = $derived.by(() => {
    void entities.value;
    const displayFeat = getDefaultDisplayFeat(entity);
    return displayFeat ? `${displayFeat} (${entity.id})` : entity.id;
  });

  let totalWidth = $derived(
    lastFrameIndex.value !== undefined
      ? (lastFrameIndex.value / (lastFrameIndex.value + 1)) * 100
      : 100,
  );
  let color = $derived(annotationColors.value.colorOfEntity(entity.id));
  let selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);

  let tracklets: Tracklet[] = $derived.by(() => {
    void annotations.value;
    return (entity.ui.childs ?? []).filter((ann) => ann.is_type(BaseSchema.Tracklet)) as Tracklet[];
  });

  let highlightState: string = $derived.by(() => {
    if (selectedToolType === ToolType.Pan) {
      return highlightedEntity.value === entity.id ? "self" : "all";
    }

    void annotations.value; // track changes
    let state = "all";
    for (const ann of entity.ui.childs ?? []) {
      if (ann.ui.displayControl.highlighted === "self") {
        return "self";
      }
      if (ann.ui.displayControl.highlighted === "none") {
        state = "none";
      }
    }
    return state;
  });

  const moveCursorToPosition = (clientX: number) => {
    const newPosition = objectTimeTrack.getBoundingClientRect();
    const newRelativePosition = (clientX - newPosition.left) / newPosition.width;
    const newFrameIndex = Math.round(newRelativePosition * (lastFrameIndex.value + 1));
    onFrameClick(newFrameIndex);
  };

  // A right-click on the empty part of the row only leaves drawing tools; a right-click on
  // a track opens its menu (TrackletSegment) and keeps the row and its focus.
  const handleTrackContextMenu = (event: MouseEvent) => {
    event.preventDefault();
    resetTool();
  };

  // Jump to the keyframe and put its track in edit mode, which keeps this row focused.
  const onEditKeyItemClick = (
    frameIndex: TrackTimelineEntry["frame_index"],
    tracklet: Tracklet,
  ) => {
    onFrameClick(frameIndex);
    editTrack(tracklet.id, { reveal: false });
  };

  const onAddKeyItemClick = (tracklet: Tracklet) => {
    const added = addKeyItemToTracklet(
      tracklet,
      entity,
      views,
      current_itemBBoxes.value,
      current_itemKeypoints.value,
    );
    if (added) {
      editTrack(tracklet.id, { reveal: false });
    }
  };

  const onSplitTrackletClick = (tracklet: Tracklet) => {
    splitTrackletAfter(tracklet, entity, currentFrameIndex.value, views);
  };

  const findNeighborItems = (tracklet: Tracklet, frameIndex: number): [number, number] => {
    return findNeighborFrameIndices(tracklet, frameIndex, tracklets);
  };

  // Pencil in the row's chip: edit mode for this object's box on the current frame.
  let currentShapes = $derived([...current_itemBBoxes.value, ...current_itemKeypoints.value]);
  let hasShapeHere = $derived(currentShapes.some((shape) => shapeTopEntityId(shape) === entity.id));
  let isEditingEntity = $derived(isEntityEditing(entity.id));
  let editBlockedReason = $derived(editModeBlockedReason());
  let editPencilTooltip = $derived.by(() => {
    if (isEditingEntity) return "Finish editing (Enter)";
    if (editBlockedReason) return editBlockedReason;
    return hasShapeHere ? "Edit this object's box (E)" : "No box on this frame";
  });
  const onEditPencilClick = () => {
    toggleEditModeForEntity(entity.id, currentShapes, { reveal: false });
  };

  const onColoredDotClick = () => {
    const newFrameIndex = highlightEntity(entity.id, highlightState === "self");
    if (newFrameIndex != currentFrameIndex.value) {
      currentFrameIndex.value = newFrameIndex;
      updateView(currentFrameIndex.value);
    }
  };

  const laneHeight = 18;
  const laneOutline = $derived.by(() => {
    if (isPrimaryFocus)
      return "border-primary/30 shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.18)]";
    if (isPinned) return "border-primary/18 shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.10)]";
    return "border-border/30";
  });
  const trackBackground = $derived.by(() => {
    if (highlightState === "self") return `${color}20`;
    if (highlightState === "none" && selectedToolType === ToolType.Fusion) return `${color}08`;
    if (isPinned) return `${color}12`;
    return `${color}0d`;
  });
</script>

{#if entity}
  <Tooltip.Root>
    <Tooltip.Trigger>
      {#snippet child({ props })}
        <section
          {...passiveTriggerProps(props)}
          class={cn("group relative transition-all", isPrimaryFocus ? "z-[1]" : "")}
          style="width: 100%;"
        >
          <div
            id={`video-object-${entity.id}`}
            class={cn(
              "relative flex gap-5 overflow-hidden rounded-md border bg-background/70",
              laneOutline,
            )}
            style={`height: ${laneHeight}px; background: ${trackBackground}`}
            bind:this={objectTimeTrack}
            role="complementary"
          >
            <div class="pointer-events-none sticky left-1 z-30 flex h-full items-center">
              <div
                class={cn(
                  "pointer-events-auto flex items-center gap-0.5 rounded-sm border bg-background/72 px-0.5 py-0.5 shadow-sm backdrop-blur-md transition-colors",
                  isPrimaryFocus
                    ? "border-primary/30"
                    : isPinned
                      ? "border-primary/25"
                      : "border-border/30",
                )}
              >
                <button
                  type="button"
                  aria-label={displayName}
                  class="h-2.5 w-2.5 rounded-full border border-background/90 shadow-sm transition-transform hover:scale-125"
                  style={`background: ${color}`}
                  onclick={onColoredDotClick}
                ></button>
                <IconButton
                  onclick={onEditPencilClick}
                  tooltipContent={editPencilTooltip}
                  selected={isEditingEntity}
                  disabled={!isEditingEntity && (editBlockedReason !== null || !hasShapeHere)}
                  class={cn("h-4 w-4 rounded-sm", !isEditingEntity && "bg-transparent")}
                >
                  <Pencil class="h-2.5 w-2.5" />
                </IconButton>
                {#if onTogglePin}
                  <div
                    class={cn(
                      "transition-opacity group-hover:opacity-100 group-focus-within:opacity-100",
                      isPinned ? "opacity-100" : "opacity-0",
                    )}
                  >
                    <IconButton
                      onclick={onTogglePin}
                      tooltipContent={isPinned ? "Unpin from timeline" : "Pin to timeline"}
                      selected={isPinned}
                      class="h-4 w-4 rounded-sm bg-transparent"
                    >
                      {#if isPinned}
                        <PushPinSlash class="h-2.5 w-2.5 text-primary" />
                      {:else}
                        <PushPin class="h-2.5 w-2.5 text-muted-foreground" />
                      {/if}
                    </IconButton>
                  </div>
                {/if}
                {#if isPinned}
                  <span class="h-1.5 w-1.5 rounded-full bg-primary/80"></span>
                {/if}
              </div>
            </div>
            <div
              class="pointer-events-none absolute inset-y-0 left-0 w-5"
              style={`background: linear-gradient(90deg, ${color}${isPrimaryFocus ? "30" : isPinned ? "20" : "16"} 0%, transparent 100%)`}
            ></div>
            <ContextMenu.Root>
              <ContextMenu.Trigger
                class="absolute left-0 h-full w-full"
                style={`width: ${totalWidth}%`}
              >
                <p oncontextmenu={handleTrackContextMenu} class="h-full w-full"></p>
              </ContextMenu.Trigger>
            </ContextMenu.Root>
            {#each tracklets as tracklet (tracklet.id)}
              <TrackletSegment
                {tracklet}
                entityId={entity.id}
                {views}
                compact={true}
                onAddKeyItemClick={() => onAddKeyItemClick(tracklet)}
                {onEditKeyItemClick}
                onSplitTrackClick={() => onSplitTrackletClick(tracklet)}
                onDeleteTrackClick={() => deleteEntity(entity, tracklet)}
                {findNeighborItems}
                {moveCursorToPosition}
                {resetTool}
              />
            {/each}
          </div>
        </section>
      {/snippet}
    </Tooltip.Trigger>
    <TooltipContent>
      <p>{displayName}</p>
    </TooltipContent>
  </Tooltip.Root>
{/if}
