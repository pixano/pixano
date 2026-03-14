<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { PushPin, PushPinSlash } from "phosphor-svelte";
  import { ToolType } from "$lib/tools";
  import type {
    TrackTimelineEntry,
    View,
  } from "$lib/ui";
  import {
    BaseSchema,
    cn,
    ContextMenu,
    Entity,
    IconButton,
    Tracklet,
  } from "$lib/ui";

  import { getTopEntity } from "$lib/utils/entityLookupUtils";
  import { deleteEntity } from "$lib/utils/entityDeletion";
  import {
    highlightEntity,
    highlightTrackletChildren,
    highlightWithEditing,
  } from "$lib/utils/highlightOperations";
  import {
    addKeyItemToTracklet,
    findNeighborFrameIndices,
    splitTracklet,
  } from "$lib/utils/trackletOperations";
  import { updateView } from "$lib/utils/videoOperations";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";
  import {
    annotations,
    colorScale,
    current_itemBBoxes,
    current_itemKeypoints,
    highlightedEntity,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import {
    currentFrameIndex,
    lastFrameIndex,
  } from "$lib/stores/videoStores.svelte";
  import TrackletSegment from "./TrackletSegment.svelte";

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
  let displayName: string = $derived.by(() => {
    const displayFeat = getDefaultDisplayFeat(entity);
    return displayFeat ? `${displayFeat} (${entity.id})` : entity.id;
  });

  let totalWidth = $derived(lastFrameIndex.value !== undefined ? (lastFrameIndex.value / (lastFrameIndex.value + 1)) * 100 : 100);
  let color = $derived(colorScale.value[1](entity.id));
  let selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);

  let tracklets: Tracklet[] = $derived(
    (entity.ui.childs ?? []).filter(
      (ann) => ann.is_type(BaseSchema.Tracklet),
    ) as Tracklet[],
  );

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

  const onContextMenu = (tracklet: Tracklet | null = null) => {
    if (tracklet && selectedToolType !== ToolType.Fusion) {
      highlightTrackletChildren(tracklet);
    }
    resetTool();
  };

  const handleTrackContextMenu = (event: MouseEvent) => {
    event.preventDefault();
    onContextMenu();
  };

  const onEditKeyItemClick = (frameIndex: TrackTimelineEntry["frame_index"], viewname: string) => {
    onFrameClick(frameIndex);
    highlightWithEditing(
      (ann) =>
        ann.data.view_name === viewname &&
        ((!ann.is_type(BaseSchema.Tracklet) &&
          getTopEntity(ann).id === entity.id &&
          ann.ui.frame_index === frameIndex) ||
          (ann.is_type(BaseSchema.Tracklet) && ann.data.entity_id === entity.id)),
    );
  };

  const onAddKeyItemClick = (tracklet: Tracklet) => {
    const added = addKeyItemToTracklet(tracklet, entity, views, current_itemBBoxes.value, current_itemKeypoints.value);
    if (added) {
      onEditKeyItemClick(currentFrameIndex.value, tracklet.data.view_name);
    }
  };

  const onSplitTrackletClick = (tracklet: Tracklet) => {
    splitTracklet(tracklet, entity.id);
  };

  const findNeighborItems = (tracklet: Tracklet, frameIndex: number): [number, number] => {
    return findNeighborFrameIndices(tracklet, frameIndex, tracklets);
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
    if (isPrimaryFocus) return "border-primary/30 shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.18)]";
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
  <section
    title={displayName}
    class={cn(
      "group relative transition-all",
      isPrimaryFocus
        ? "z-[1]"
        : "",
    )}
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
            isPrimaryFocus ? "border-primary/30" : isPinned ? "border-primary/25" : "border-border/30",
          )}
        >
          <button
            type="button"
            class="h-2.5 w-2.5 rounded-full border border-background/90 shadow-sm transition-transform hover:scale-125"
            style={`background: ${color}`}
            title={displayName}
            onclick={onColoredDotClick}
          ></button>
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
      <div class="pointer-events-none absolute inset-y-0 left-0 w-5" style={`background: linear-gradient(90deg, ${color}${isPrimaryFocus ? "30" : isPinned ? "20" : "16"} 0%, transparent 100%)`}></div>
      <ContextMenu.Root>
        <ContextMenu.Trigger class="absolute left-0 h-full w-full" style={`width: ${totalWidth}%`}>
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
          {onContextMenu}
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
{/if}
