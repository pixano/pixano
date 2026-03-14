<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ToolType } from "$lib/tools";
  import { Button } from "bits-ui";

  import {
    Annotation,
    BaseSchema,
    cn,
    ContextMenu,
    SequenceFrame,
    Tracklet,
    View,
    type TrackTimelineEntry,
  } from "$lib/ui";

  import { saveTo } from "$lib/utils/saveItemUtils";
  import { sortByFrameIndex } from "$lib/utils/videoUtils";
  import { applyPixanoSourceFields, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { relink } from "$lib/utils/entityRelink";
  import { getWorkspaceContext } from "$lib/workspace/context";
  import {
    annotations,
    colorScale,
    entities,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";
  import KeyframeDot from "./KeyframeDot.svelte";

  type MView = Record<string, View | View[]>;

  interface Props {
    entityId: string;
    tracklet: Tracklet;
    views: MView;
    compact?: boolean;
    onContextMenu: (tracklet: Tracklet) => void;
    onEditKeyItemClick: (
    frameIndex: TrackTimelineEntry["frame_index"],
    viewname: string,
  ) => void;
    onAddKeyItemClick: (event: MouseEvent) => void;
    onSplitTrackClick: () => void;
    onDeleteTrackClick: () => void;
    findNeighborItems: (tracklet: Tracklet, frameIndex: number) => [number, number];
    moveCursorToPosition: (clientX: number) => void;
    resetTool: () => void;
  }

  let {
    entityId,
    tracklet = $bindable(),
    views,
    compact = false,
    onContextMenu,
    onEditKeyItemClick,
    onAddKeyItemClick,
    onSplitTrackClick,
    onDeleteTrackClick,
    findNeighborItems,
    moveCursorToPosition,
    resetTool
  }: Props = $props();
  const { manifest } = getWorkspaceContext();

  let showRelink = $state(false);
  let selectedEntityId = $state("new");
  let mustMerge: boolean = $state(false);
  let overlapTargetId: string = $state("");
  const defaultButtonClass =
    "inline-flex items-center justify-center rounded-lg text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2";

  const track_margin = 0.3;
  const getLeft = (trk: Tracklet) => {
    let start = Math.max(0, trk.data.start_frame - track_margin);
    return (start / (lastFrameIndex.value + 1)) * 100;
  };
  const getRight = (trk: Tracklet) => {
    let end = Math.max(trk.data.start_frame, trk.data.end_frame) + track_margin;
    return (end / (lastFrameIndex.value + 1)) * 100;
  };
  const getHeight = (views: MView, compactLane: boolean) => {
    if (compactLane) return 72;
    return 80 / Object.keys(views).length;
  };
  const getTop = (trk: Tracklet, views: MView) => {
    if (compact) return 14;
    return (
      10 +
      (80 * Object.keys(views).indexOf(trk.data.view_name)) / Object.keys(views).length
    );
  };

  let left = $derived(getLeft(tracklet));
  let right = $derived(getRight(tracklet));
  let height = $derived(getHeight(views, compact));
  let top = $derived(getTop(tracklet, views));
  let trackElement: HTMLElement = $state();

  let resizeObs: ResizeObserver = $state();
  let oneFrameInPixel: number = $state();
  const calcOneFrameInPixel = () => {
    oneFrameInPixel =
      trackElement?.getBoundingClientRect().width /
      (tracklet.data.end_frame - tracklet.data.start_frame + 1);
  };
  calcOneFrameInPixel();

  $effect(() => {
    if (resizeObs) {
      if (tracklet.ui.displayControl.highlighted === "self") {
        resizeObs.observe(trackElement);
      } else {
        resizeObs.unobserve(trackElement);
      }
    }
  });
  $effect(() => {
    const obs = new ResizeObserver(calcOneFrameInPixel);
    resizeObs = obs;
    return () => obs.disconnect();
  });

  let color = $derived(colorScale.value[1](entityId));
  let selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);

  let keyframeIndexes = $derived((tracklet.ui.childs ?? []).map((ann) => ann.ui.frame_index));

  let canAddKeyFrame =
    $derived(currentFrameIndex.value > tracklet.data.start_frame &&
    currentFrameIndex.value <tracklet.data.end_frame &&
    !(tracklet.ui.childs ?? []).some((ann) => ann.ui.frame_index === currentFrameIndex.value));

  let canSplit =
    $derived(currentFrameIndex.value >= tracklet.data.start_frame &&
    currentFrameIndex.value <tracklet.data.end_frame);

  const getNeighborTracklet = (
    allAnnotations: Annotation[],
    direction: "left" | "right",
  ): Annotation | null => {
    const isLeft = direction === "left";

    const refCompareTimestep = isLeft ? tracklet.data.start_frame : tracklet.data.end_frame;

    const neighborTracklets = allAnnotations.filter((ann) => {
      if (!ann.is_type(BaseSchema.Tracklet)) return false;
      const t = ann as Tracklet;
      return (
        t.data.view_name === tracklet.data.view_name &&
        t.data.entity_id === entityId &&
        (isLeft
          ? t.data.end_frame <refCompareTimestep
          : t.data.start_frame > refCompareTimestep)
      );
    });

    if (neighborTracklets.length === 0) return null;

    return neighborTracklets.reduce((best, curr) => {
      const tBest = best as Tracklet;
      const tCurr = curr as Tracklet;

      const bestVal = isLeft ? tBest.data.end_frame : tBest.data.start_frame;
      const currVal = isLeft ? tCurr.data.end_frame : tCurr.data.start_frame;

      return isLeft
        ? currVal > bestVal
          ? curr
          : best
        : currVal <bestVal
          ? curr
          : best;
    });
  };

  const canContinueDragging = (newFrameIndex: number, draggedFrameIndex: number): boolean => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborItems(tracklet, draggedFrameIndex);
    if (
      (prevFrameIndex !== 0 && newFrameIndex <prevFrameIndex + 1) ||
      (nextFrameIndex !== lastFrameIndex.value && newFrameIndex > nextFrameIndex - 1)
    )
      return false;
    const isStart = draggedFrameIndex === tracklet.data.start_frame;
    const isEnd = draggedFrameIndex === tracklet.data.end_frame;
    if (!(isStart || isEnd)) return false;
    if (isStart) {
      if (newFrameIndex >= tracklet.data.end_frame) return false;
      left = (newFrameIndex / (lastFrameIndex.value + 1)) * 100;
      right = (tracklet.data.end_frame / (lastFrameIndex.value + 1)) * 100;
    }
    if (isEnd) {
      if (newFrameIndex <= tracklet.data.start_frame) return false;
      right = (newFrameIndex / (lastFrameIndex.value + 1)) * 100;
    }
    return true;
  };

  const updateTrackletWidth = (newFrameIndex: number, draggedFrameIndex: number) => {
    const isStart = draggedFrameIndex === tracklet.data.start_frame;
    const isEnd = draggedFrameIndex === tracklet.data.end_frame;
    const viewFrames = views[tracklet.data.view_name] as SequenceFrame[] | undefined;
    if (!viewFrames?.[newFrameIndex] || !tracklet.ui.childs?.length) return;
    const newViewId = viewFrames[newFrameIndex].id;
    let movedAnn = tracklet.ui.childs[0];
    if (isStart) tracklet.data.start_frame = newFrameIndex;
    if (isEnd) {
      movedAnn = tracklet.ui.childs[tracklet.ui.childs.length - 1];
      tracklet.data.end_frame = newFrameIndex;
    }
    movedAnn.ui.frame_index = newFrameIndex;
    movedAnn.data.frame_id = newViewId;

    annotations.update((objects) =>
      objects.map((ann) => {
        if (ann.is_type(BaseSchema.Tracklet) && ann.id === tracklet.id) {
          if (isStart) {
            (ann as Tracklet).data.start_frame = newFrameIndex;
          }
          if (isEnd) {
            (ann as Tracklet).data.end_frame = newFrameIndex;
          }
        }
        if (ann.id === movedAnn.id) {
          ann.ui.frame_index = newFrameIndex;
          ann.data.frame_id = newViewId;
        }
        return ann;
      }),
    );
    applyPixanoSourceFields(tracklet);
    saveTo("update", tracklet);
    applyPixanoSourceFields(movedAnn);
    saveTo("update", movedAnn);
    currentFrameIndex.value = newFrameIndex;
  };

  let leftNeighbor = $derived(getNeighborTracklet(annotations.value, "left"));
  let rightNeighbor = $derived(getNeighborTracklet(annotations.value, "right"));

  const onGlueTrackletClick = (direction: "left" | "right") => {
    const neighbor = direction === "left" ? leftNeighbor : rightNeighbor;
    if (!neighbor) return;

    annotations.update((anns) => {
      let filteredAnns = anns.filter((ann) => ann.id !== neighbor.id);
      return filteredAnns.map((ann) => {
        if (ann.id === tracklet.id) {
          const currentTracklet = ann as Tracklet;
          const neighborTracklet = neighbor as Tracklet;

          currentTracklet.ui.childs = [
            ...currentTracklet.ui.childs,
            ...neighborTracklet.ui.childs,
          ].sort(sortByFrameIndex);

          if (direction === "left") {
            currentTracklet.data.start_frame = neighborTracklet.data.start_frame;
          } else {
            currentTracklet.data.end_frame = neighborTracklet.data.end_frame;
          }
        }
        return ann;
      });
    });

    entities.update((ents) =>
      ents.map((ent) => {
        if (ent.id === entityId) {
          ent.ui.childs = ent.ui.childs?.filter((ann) => ann.id !== neighbor.id);
        }
        return ent;
      }),
    );

    saveTo("delete", neighbor);
  };

  const onClick = (button: number, clientX: number) => {
    if (button === 0) {
      moveCursorToPosition(clientX);
      resetTool();
    }
  };

  const handleTrackContextMenu = (event: MouseEvent) => {
    event.preventDefault();
    onContextMenu(tracklet);
  };

  const onRelinkTrackClick = (event: MouseEvent) => {
    event.preventDefault();
    showRelink = !showRelink;
  };

  const handleRelink = () => {
    relink(tracklet, getTopEntity(tracklet), selectedEntityId, mustMerge, overlapTargetId, manifest);
    showRelink = false;
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("video-tracklet absolute scale-y-90 rounded-sm", {
      "opacity-100": tracklet.ui.displayControl.highlighted === "self",
      "opacity-30":
        (tracklet.ui.displayControl.highlighted === "none" &&
          selectedToolType === ToolType.Fusion) ||
        tracklet.ui.displayControl.hidden,
    })}
    style={`left: ${left}%; width: ${right - left}%; top: ${top}%; height: ${height}%; background-color: ${color}`}
  >
    <button
      oncontextmenu={handleTrackContextMenu}
      aria-label="Track segment handle"
      class="absolute h-full w-full"
      bind:this={trackElement}
      onclick={(e) => onClick(e.button, e.clientX)}
></button>
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    {#if selectedToolType === ToolType.Fusion}
      <ContextMenu.Item>Context options disabled while in association mode</ContextMenu.Item>
    {:else}
      {#if canAddKeyFrame}
        <ContextMenu.Item onclick={(event) => onAddKeyItemClick(event)}>
          Add a point at frame {currentFrameIndex.value}
        </ContextMenu.Item>
      {/if}
      {#if canSplit}
        <ContextMenu.Item onclick={onSplitTrackClick}>
          Split track after frame {currentFrameIndex.value}
        </ContextMenu.Item>
      {/if}
      {#if leftNeighbor}
        <ContextMenu.Item onclick={() => onGlueTrackletClick("left")}>
          Glue to left
        </ContextMenu.Item>
      {/if}
      {#if rightNeighbor}
        <ContextMenu.Item onclick={() => onGlueTrackletClick("right")}>
          Glue to right
        </ContextMenu.Item>
      {/if}
      <ContextMenu.Item onclick={onRelinkTrackClick}>Relink track</ContextMenu.Item>
      <ContextMenu.Item onclick={onDeleteTrackClick}>Delete track</ContextMenu.Item>
      {#if showRelink}
        <div class="flex flex-row gap-4 items-center mr-4">
          <RelinkAnnotation
            bind:selectedEntityId
            bind:mustMerge
            bind:overlapTargetId
            baseSchema={tracklet.table_info.base_schema}
            viewRef={{ name: tracklet.data.view_name, id: tracklet.data.frame_id }}
            track={tracklet}
          />
          <Button.Root type="button" class={cn(defaultButtonClass, "text-white mt-4")} onclick={handleRelink}>
            OK
          </Button.Root>
        </div>
      {/if}
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
{#if tracklet.ui.displayControl.highlighted === "self" && oneFrameInPixel > 15}
  {#key keyframeIndexes.length}
    {#each keyframeIndexes as itemFrameIndex}
      <KeyframeDot
        {itemFrameIndex}
        tracklet={tracklet}
        {color}
        {height}
        {top}
        {oneFrameInPixel}
        {onEditKeyItemClick}
        {onClick}
        {entityId}
        {canContinueDragging}
        updateTrackletWidth={updateTrackletWidth}
        {resetTool}
      />
    {/each}
  {/key}
{/if}
