<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu } from "@pixano/core";
  import type {
    Tracklet,
    TrackletItem,
    TrackletWithItems,
    VideoItemBBox,
    VideoObject,
  } from "@pixano/core";
  import { itemObjects, selectedTool } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    objectIdBeingEdited,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import {
    addKeyItem,
    deleteTracklet,
    mapSplittedTrackToObject,
    mapTrackItemsToObject,
    splitTrackletInTwo,
  } from "../../lib/api/videoApi";
  import ObjectTracklet from "./ObjectTracklet.svelte";
  import { panTool } from "../../lib/settings/selectionTools";
  import { highlightCurrentObject } from "../../lib/api/objectsApi";
  import { onMount } from "svelte";

  export let object: VideoObject;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let updateView: (frameIndex: number, track: Tracklet[] | undefined) => void;

  let rightClickFrameIndex: number;
  let objectTimeTrack: HTMLElement;
  let trackWithItems: TrackletWithItems[];

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;

  const moveCursorToPosition = (clientX: number) => {
    const timeTrackPosition = objectTimeTrack.getBoundingClientRect();
    const rightClickFrame = (clientX - timeTrackPosition.left) / timeTrackPosition.width;
    rightClickFrameIndex = Math.round(rightClickFrame * $lastFrameIndex);
    onTimeTrackClick(rightClickFrameIndex);
  };

  const onContextMenu = (event: MouseEvent) => {
    itemObjects.update((oldObjects) => highlightCurrentObject(oldObjects, object));
    moveCursorToPosition(event.clientX);
    selectedTool.set(panTool);
  };

  const onEditKeyItemClick = (frameIndex: TrackletItem["frame_index"]) => {
    onTimeTrackClick(frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex);
    objectIdBeingEdited.set(object.id);
    itemObjects.update((objects) =>
      objects.map((obj) => {
        obj.highlighted = obj.id === object.id ? "self" : "none";
        obj.displayControl = {
          ...obj.displayControl,
          editing: obj.id === object.id,
        };
        return obj;
      }),
    );
  };

  const onAddKeyItemClick = () => {
    trackWithItems = addKeyItem(rightClickFrameIndex, $lastFrameIndex, trackWithItems);
    itemObjects.update((objects) =>
      objects.map((obj) => {
        if (obj.id === object.id && obj.datasetItemType === "video") {
          const { boxes, keypoints } = mapTrackItemsToObject(
            trackWithItems,
            object,
            rightClickFrameIndex,
          );
          return { ...obj, track: trackWithItems, boxes, keypoints };
        }
        return obj;
      }),
    );
    onEditKeyItemClick(rightClickFrameIndex);
  };

  const onSplitTrackletClick = (trackletIndex: number) => {
    trackWithItems = splitTrackletInTwo(trackWithItems, trackletIndex, rightClickFrameIndex);
    itemObjects.update((objects) =>
      objects.map((obj) => {
        if (obj.id === object.id && obj.datasetItemType === "video") {
          const { boxes, keypoints } = mapSplittedTrackToObject(
            trackWithItems,
            object,
            rightClickFrameIndex,
          );
          return { ...obj, track: trackWithItems, boxes, keypoints };
        }
        return obj;
      }),
    );
  };

  const onDeleteTrackletClick = (trackletIndex: number) => {
    itemObjects.update((objects) =>
      deleteTracklet(objects, object.id, trackletIndex, trackWithItems),
    );
  };

  const findNeighborItems = (frameIndex: VideoItemBBox["frame_index"]): [number, number] => {
    const allItems = trackWithItems.reduce(
      (acc, tracklet) => [...acc, ...tracklet.items],
      [] as TrackletItem[],
    );
    const nextItem =
      allItems.find((item) => item.frame_index > frameIndex && item.is_key)?.frame_index ||
      $lastFrameIndex;
    const prevItem =
      allItems
        .slice()
        .reverse()
        .find((item) => item.frame_index < frameIndex && item.is_key)?.frame_index || 0;

    return [prevItem, nextItem];
  };

  const getTrackletItem = (ann: TrackletItem) => {
      let item: TrackletItem = {
        frame_index: ann.frame_index,
        tracklet_id: ann.tracklet_id,
      };
      if (ann.is_key) item.is_key = ann.is_key;
      if (ann.is_thumbnail) item.is_thumbnail = ann.is_thumbnail;
      if (ann.hidden) item.hidden = ann.hidden;
      return item;
    };

  const updateTracks = () => {
    trackWithItems = [];
    for (const tracklet of object.track) {
      const boxes = object.boxes
        ? object.boxes.filter(
            (box) =>
              box.view_id == tracklet.view_id &&
              box.frame_index >= tracklet.start &&
              box.frame_index <= tracklet.end,
          )
        : [];
      const keypoints = object.keypoints
        ? object.keypoints.filter(
            (kp) =>
              kp.view_id == tracklet.view_id &&
              kp.frame_index >= tracklet.start &&
              kp.frame_index <= tracklet.end,
          )
        : [];
      let items: TrackletItem[] = [];
      for (const ann of boxes) {
        items.push(getTrackletItem(ann));
      }
      for (const ann of keypoints) {
        const item = getTrackletItem(ann);
        if (!items.find((it) => it.frame_index == item.frame_index))
          items.push(getTrackletItem(ann));
      }
      trackWithItems.push({
        ...tracklet,
        items: items,
      });
    }
  };

  onMount(() => {
    updateTracks();
  });
</script>

{#if trackWithItems}
  <div
    class="flex gap-5 relative h-12 my-auto z-20"
    id={`video-object-${object.id}`}
    style={`width: ${$videoControls.zoomLevel[0]}%`}
    bind:this={objectTimeTrack}
    role="complementary"
  >
    <span
      class="w-[1px] bg-primary h-full absolute top-0 z-30 pointer-events-none"
      style={`left: ${($currentFrameIndex / ($lastFrameIndex + 1)) * 100}%`}
    />
    <ContextMenu.Root>
      <ContextMenu.Trigger class="h-full w-full absolute left-0" style={`width: ${totalWidth}%`}>
        <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
      </ContextMenu.Trigger>
      <ContextMenu.Content>
        <ContextMenu.Item inset on:click={onAddKeyItemClick}>Add a point</ContextMenu.Item>
      </ContextMenu.Content>
    </ContextMenu.Root>
    {#each trackWithItems as tracklet, i}
      <ObjectTracklet
        {tracklet}
        {object}
        {onAddKeyItemClick}
        {onContextMenu}
        {onEditKeyItemClick}
        onSplitTrackletClick={() => onSplitTrackletClick(i)}
        onDeleteTrackletClick={() => onDeleteTrackletClick(i)}
        {findNeighborItems}
        {updateView}
        {moveCursorToPosition}
      />
    {/each}
  </div>
{/if}
