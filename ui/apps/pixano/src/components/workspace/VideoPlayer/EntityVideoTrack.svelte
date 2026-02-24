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
    buttonVariants,
    cn,
    ContextMenu,
    SequenceFrame,
    Track,
    View,
    type TrackTimelineEntry,
  } from "$lib/ui";

  import { sourcesStore } from "$lib/stores/appStores.svelte";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { sortByFrameIndex } from "$lib/utils/videoUtils";
  import { getPixanoSource, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { relink } from "$lib/utils/entityMutations";
  import {
    annotations,
    colorScale,
    entities,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";
  import TrackKeyItem from "./TrackKeyItem.svelte";

  type MView = Record<string, View | View[]>;

  interface Props {
    trackId: string;
    track: Track;
    views: MView;
    onContextMenu: (track: Track) => void;
    onEditKeyItemClick: (
    frameIndex: TrackTimelineEntry["frame_index"],
    viewname: string,
  ) => void;
    onAddKeyItemClick: (event: MouseEvent) => void;
    onSplitTrackClick: () => void;
    onDeleteTrackClick: () => void;
    findNeighborItems: (track: Track, frameIndex: number) => [number, number];
    moveCursorToPosition: (clientX: number) => void;
    resetTool: () => void;
  }

  let {
    trackId,
    track: videoTrack = $bindable(),
    views,
    onContextMenu,
    onEditKeyItemClick,
    onAddKeyItemClick,
    onSplitTrackClick,
    onDeleteTrackClick,
    findNeighborItems,
    moveCursorToPosition,
    resetTool
  }: Props = $props();

  let showRelink = $state(false);
  let selectedEntityId = $state("new");
  let mustMerge: boolean = $state(false);
  let overlapTargetId: string = $state("");

  const track_margin = 0.3;
  const getLeft = (trk: Track) => {
    let start = Math.max(0, trk.data.start_frame - track_margin);
    return (start / (lastFrameIndex.value + 1)) * 100;
  };
  const getRight = (trk: Track) => {
    let end = Math.max(trk.data.start_frame, trk.data.end_frame) + track_margin;
    return (end / (lastFrameIndex.value + 1)) * 100;
  };
  const getHeight = (views: MView) => 80 / Object.keys(views).length;
  const getTop = (trk: Track, views: MView) => {
    return (
      10 +
      (80 * Object.keys(views).indexOf(trk.data.view_name)) / Object.keys(views).length
    );
  };

  let left = $derived(getLeft(videoTrack));
  let right = $derived(getRight(videoTrack));
  let height = $derived(getHeight(views));
  let top = $derived(getTop(videoTrack, views));
  let trackElement: HTMLElement = $state();

  let resizeObs: ResizeObserver = $state();
  let oneFrameInPixel: number = $state();
  const calcOneFrameInPixel = () => {
    oneFrameInPixel =
      trackElement?.getBoundingClientRect().width /
      (videoTrack.data.end_frame - videoTrack.data.start_frame + 1);
  };
  calcOneFrameInPixel();

  $effect(() => {
    if (resizeObs) {
      if (videoTrack.ui.displayControl.highlighted) {
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

  let color = $derived(colorScale.value[1](trackId));

  let track_annotations_frame_indexes = $derived((videoTrack.ui.childs ?? []).map((ann) => ann.ui.frame_index));

  let canAddKeyFrame =
    $derived(currentFrameIndex.value > videoTrack.data.start_frame &&
    currentFrameIndex.value < videoTrack.data.end_frame &&
    !(videoTrack.ui.childs ?? []).some((ann) => ann.ui.frame_index === currentFrameIndex.value));

  let canSplit =
    $derived(currentFrameIndex.value >= videoTrack.data.start_frame &&
    currentFrameIndex.value < videoTrack.data.end_frame);

  const getNeighborTrack = (
    annotations: Annotation[],
    direction: "left" | "right",
  ): Annotation | null => {
    const isLeft = direction === "left";

    const refCompareTimestep = isLeft ? videoTrack.data.start_frame : videoTrack.data.end_frame;

    const neighborTracks = annotations.filter((ann) => {
      if (!ann.is_type(BaseSchema.Tracklet)) return false;
      const t = ann as Track;
      return (
        t.data.view_name === videoTrack.data.view_name &&
        t.data.entity_id === trackId &&
        (isLeft
          ? t.data.end_frame < refCompareTimestep
          : t.data.start_frame > refCompareTimestep)
      );
    });

    if (neighborTracks.length === 0) return null;

    return neighborTracks.reduce((best, curr) => {
      const tBest = best as Track;
      const tCurr = curr as Track;

      const bestVal = isLeft ? tBest.data.end_frame : tBest.data.start_frame;
      const currVal = isLeft ? tCurr.data.end_frame : tCurr.data.start_frame;

      return isLeft
        ? currVal > bestVal
          ? curr
          : best // max for "left"
        : currVal < bestVal
          ? curr
          : best; // min for "right"
    });
  };

  const canContinueDragging = (newFrameIndex: number, draggedFrameIndex: number): boolean => {
    const [prevFrameIndex, nextFrameIndex] = findNeighborItems(videoTrack, draggedFrameIndex);
    if (
      (prevFrameIndex !== 0 && newFrameIndex < prevFrameIndex + 1) ||
      (nextFrameIndex !== lastFrameIndex.value && newFrameIndex > nextFrameIndex - 1)
    )
      return false;
    const isStart = draggedFrameIndex === videoTrack.data.start_frame;
    const isEnd = draggedFrameIndex === videoTrack.data.end_frame;
    if (!(isStart || isEnd)) return false;
    if (isStart) {
      if (newFrameIndex >= videoTrack.data.end_frame) return false;
      left = (newFrameIndex / (lastFrameIndex.value + 1)) * 100;
      right = (videoTrack.data.end_frame / (lastFrameIndex.value + 1)) * 100;
    }
    if (isEnd) {
      if (newFrameIndex <= videoTrack.data.start_frame) return false;
      right = (newFrameIndex / (lastFrameIndex.value + 1)) * 100;
    }
    return true;
  };

  const updateTrackWidth = (newFrameIndex: number, draggedFrameIndex: number) => {
    const isStart = draggedFrameIndex === videoTrack.data.start_frame;
    const isEnd = draggedFrameIndex === videoTrack.data.end_frame;
    const viewFrames = views[videoTrack.data.view_name] as SequenceFrame[] | undefined;
    if (!viewFrames?.[newFrameIndex] || !videoTrack.ui.childs?.length) return;
    const newViewId = viewFrames[newFrameIndex].id;
    let movedAnn = videoTrack.ui.childs[0];
    if (isStart) videoTrack.data.start_frame = newFrameIndex;
    if (isEnd) {
      movedAnn = videoTrack.ui.childs[videoTrack.ui.childs.length - 1];
      videoTrack.data.end_frame = newFrameIndex;
    }
    movedAnn.ui.frame_index = newFrameIndex;
    movedAnn.data.frame_id = newViewId;

    annotations.update((objects) =>
      objects.map((ann) => {
        if (ann.is_type(BaseSchema.Tracklet) && ann.id === videoTrack.id) {
          if (isStart) {
            (ann as Track).data.start_frame = newFrameIndex;
          }
          if (isEnd) {
            (ann as Track).data.end_frame = newFrameIndex;
          }
        }
        if (ann.id === movedAnn.id) {
          ann.ui.frame_index = newFrameIndex;
          ann.data.frame_id = newViewId;
        }
        return ann;
      }),
    );
    const pixSource = getPixanoSource(sourcesStore);
    videoTrack.data.source_id = pixSource.id;
    saveTo("update", videoTrack);
    movedAnn.data.source_id = pixSource.id;
    saveTo("update", movedAnn);
    currentFrameIndex.value = newFrameIndex;
  };

  let leftTrack = $derived(getNeighborTrack(annotations.value, "left"));
  let rightTrack = $derived(getNeighborTrack(annotations.value, "right"));

  const onGlueTrackClick = (direction: "left" | "right") => {
    const neighbor = direction === "left" ? leftTrack : rightTrack;
    if (!neighbor) return;

    annotations.update((anns) => {
      // Remove neighbor
      let new_anns = anns.filter((ann) => ann.id !== neighbor.id);
      return new_anns.map((ann) => {
        if (ann.id === videoTrack.id) {
          const currentTrack = ann as Track;
          const neighborTrack = neighbor as Track;

          // Add neighbor's childs
          currentTrack.ui.childs = [
            ...currentTrack.ui.childs,
            ...neighborTrack.ui.childs,
          ].sort(sortByFrameIndex);

          // Update range
          if (direction === "left") {
            currentTrack.data.start_frame = neighborTrack.data.start_frame;
          } else {
            currentTrack.data.end_frame = neighborTrack.data.end_frame;
          }
        }
        return ann;
      });
    });

    entities.update((ents) =>
      ents.map((ent) => {
        if (ent.id === trackId) {
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
    onContextMenu(videoTrack);
  };

  const onRelinkTrackClick = (event: MouseEvent) => {
    event.preventDefault(); //avoid context menu close
    showRelink = !showRelink;
  };

  const handleRelink = () => {
    relink(videoTrack, getTopEntity(videoTrack), selectedEntityId, mustMerge, overlapTargetId);
    showRelink = false;
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn("video-tracklet absolute scale-y-90 rounded-sm", {
      "opacity-100": videoTrack.ui.displayControl.highlighted === "self",
      "opacity-30":
        (videoTrack.ui.displayControl.highlighted === "none" &&
          selectedTool.value.type === ToolType.Fusion) ||
        videoTrack.ui.displayControl.hidden,
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
    {#if selectedTool.value.type === ToolType.Fusion}
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
      {#if leftTrack}
        <ContextMenu.Item onclick={() => onGlueTrackClick("left")}>
          Glue to left
        </ContextMenu.Item>
      {/if}
      {#if rightTrack}
        <ContextMenu.Item onclick={() => onGlueTrackClick("right")}>
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
            baseSchema={videoTrack.table_info.base_schema}
            viewRef={{ name: videoTrack.data.view_name, id: videoTrack.data.frame_id }}
            track={videoTrack}
          />
          <Button.Root type="button" class={cn(buttonVariants(), "text-white mt-4")} onclick={handleRelink}>OK</Button.Root>
        </div>
      {/if}
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
{#if videoTrack.ui.displayControl.highlighted === "self" && oneFrameInPixel > 15}
  {#key track_annotations_frame_indexes.length}
    {#each track_annotations_frame_indexes as itemFrameIndex}
      <TrackKeyItem
        {itemFrameIndex}
        track={videoTrack}
        {color}
        {height}
        {top}
        {oneFrameInPixel}
        {onEditKeyItemClick}
        {onClick}
        {trackId}
        {canContinueDragging}
        updateTrackWidth={updateTrackWidth}
        {resetTool}
      />
    {/each}
  {/key}
{/if}
