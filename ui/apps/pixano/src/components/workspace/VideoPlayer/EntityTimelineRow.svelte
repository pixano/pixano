<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

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
    timelineZoom,
  } from "$lib/stores/videoStores.svelte";
  import TrackletSegment from "./TrackletSegment.svelte";

  type MView = Record<string, View | View[]>;

  interface Props {
    entity: Entity;
    views: MView;
    onFrameClick: (imageIndex: number) => void;
    resetTool: () => void;
  }

  let {
    entity,
    views,
    onFrameClick,
    resetTool
  }: Props = $props();

  let objectTimeTrack: HTMLElement = $state();
  let displayName: string = $derived.by(() => {
    const displayFeat = getDefaultDisplayFeat(entity);
    return displayFeat ? `${displayFeat} (${entity.id})` : entity.id;
  });

  let totalWidth = $derived((lastFrameIndex.value / (lastFrameIndex.value + 1)) * 100);
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
</script>

{#if entity}
  <div style={`width: ${timelineZoom.value[0]}%;`}>
    <div
      class={cn("w-fit sticky left-5 my-1 px-1 border-2 rounded-sm", {
        "text-foreground": highlightState !== "none",
        "text-muted-foreground":
          highlightState === "none" && selectedToolType === ToolType.Fusion,
      })}
      style={`
        background: ${
          highlightState === "self"
            ? `${color}8a`
            : highlightState === "none" && selectedToolType === ToolType.Fusion
              ? "white"
              : `${color}3a`
        };
        border-color:${highlightState === "self" ? color : "transparent"}
      `}
    >
      <button
        class="rounded-full border w-3 h-3"
        style="background:{color}"
        title="Highlight object"
        onclick={onColoredDotClick}
></button>
      <span title="{entity.table_info.base_schema} ({entity.id})">
        {displayName}
      </span>
    </div>
  </div>
  <div
    id={`video-object-${entity.id}`}
    class="flex gap-5 relative my-auto z-20 border-2 rounded-sm"
    style={`
      width: ${timelineZoom.value[0]}%;
      height: ${Object.keys(views).length * 10}px;
      background: ${
        highlightState === "self"
          ? `${color}8a`
          : highlightState === "none" && selectedToolType === ToolType.Fusion
            ? `${color}0a`
            : `${color}3a`
      };
      border-color:${highlightState === "self" ? color : "transparent"}
    `}
    bind:this={objectTimeTrack}
    role="complementary"
  >
    <span
      class="w-[1px] bg-primary h-full absolute top-0 z-30 pointer-events-none"
      style={`left: ${(currentFrameIndex.value / (lastFrameIndex.value + 1)) * 100}%`}
></span>
    <ContextMenu.Root>
      <ContextMenu.Trigger class="h-full w-full absolute left-0" style={`width: ${totalWidth}%`}>
        <p oncontextmenu={handleTrackContextMenu} class="h-full w-full"></p>
      </ContextMenu.Trigger>
      <!--  //TODO we don't allow adding a point outside of a tracklet right now
            //you can extend tracket to add a point inside, and split if needed
      <ContextMenu.Content>
        <ContextMenu.Item onclick={onAddKeyItemClick}>Add a point</ContextMenu.Item>
      </ContextMenu.Content>
      -->
    </ContextMenu.Root>
    {#each tracklets as tracklet (tracklet.id)}
      <TrackletSegment
        {tracklet}
        entityId={entity.id}
        {views}
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
{/if}
