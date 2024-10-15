<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, Track, Tracklet } from "@pixano/core";
  import type {
    SequenceFrame,
    TrackletItem,
    MView,
    // TrackletWithItems,
    // VideoItemBBox,
    // VideoObject,
  } from "@pixano/core";
  import { annotations, selectedTool, canSave } from "../../lib/stores/datasetItemWorkspaceStores";
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

  export let track: Track;
  export let views: MView;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let updateView: (frameIndex: number, track: Tracklet[] | undefined) => void;

  let rightClickFrameIndex: number;
  let objectTimeTrack: HTMLElement;
  let tracklets: Tracklet[];

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;

  $: if (track) {
    tracklets = $annotations.filter(
      (ann) => ann.is_tracklet && ann.data.entity_ref.id === track.id,
    ) as Tracklet[];
  }

  const moveCursorToPosition = (clientX: number) => {
    const timeTrackPosition = objectTimeTrack.getBoundingClientRect();
    const rightClickFrame = (clientX - timeTrackPosition.left) / timeTrackPosition.width;
    rightClickFrameIndex = Math.round(rightClickFrame * $lastFrameIndex);
    onTimeTrackClick(rightClickFrameIndex);
  };

  const onContextMenu = (event: MouseEvent) => {
    annotations.update((oldObjects) => highlightCurrentObject(oldObjects, track));
    moveCursorToPosition(event.clientX);
    selectedTool.set(panTool);
  };

  const onEditKeyItemClick = (frameIndex: TrackletItem["frame_index"]) => {
    onTimeTrackClick(frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex);
    objectIdBeingEdited.set(track.id); //TODO not track id ! change that
    annotations.update((objects) =>
      objects.map((obj) => {
        obj.highlighted = obj.id === track.id ? "self" : "none";
        obj.displayControl = {
          ...obj.displayControl,
          editing: obj.id === track.id,
        };
        return obj;
      }),
    );
  };

  const onAddKeyItemClick = (tracklet: TrackletWithItems | MouseEvent) => {
    if ("view_id" in tracklet) {
      trackWithItems = addKeyItem(
        rightClickFrameIndex,
        $lastFrameIndex,
        trackWithItems,
        tracklet.view_id,
      );
      annotations.update((objects) =>
        objects.map((obj) => {
          if (obj.id === track.id && obj.datasetItemType === "video") {
            const { boxes, keypoints } = mapTrackItemsToObject(
              trackWithItems,
              track,
              rightClickFrameIndex,
            );
            return { ...obj, track: trackWithItems, boxes, keypoints };
          }
          return obj;
        }),
      );
      //svelte hack to detect change in trackWithItems -- it requires a for-in loop
      // eslint-disable-next-line
      for (const i in trackWithItems) {
        trackWithItems[i] = { ...trackWithItems[i] }; //destructuration required, else optimizer(?) remove it...
      }

      onEditKeyItemClick(rightClickFrameIndex);
      canSave.set(true);
    } else {
      //MouseEvent, need to determine view_id
      //TODO
      confirm("Adding a key point outside of a tracklet is forbidden for now");
    }
  };

  //like findNeighborItems, but "better" (return existing neighbors)
  const findPreviousAndNext = (items: TrackletItem[], targetIndex: number): [number, number] => {
    let low = 0;
    let high = items.length - 1;
    let mid;
    let previousItem: TrackletItem | null = null;
    let nextItem: TrackletItem | null = null;

    while (low <= high) {
      mid = Math.floor((low + high) / 2);
      if (items[mid].frame_index <= targetIndex) {
        previousItem = items[mid];
        low = mid + 1;
      } else {
        nextItem = items[mid];
        high = mid - 1;
      }
    }
    return [
      previousItem ? previousItem.frame_index : targetIndex,
      nextItem ? nextItem.frame_index : targetIndex + 1,
    ];
  };

  const onSplitTrackletClick = (tracklet: TrackletWithItems) => {
    const [prev, next] = findPreviousAndNext(tracklet.items, rightClickFrameIndex);
    trackWithItems = splitTrackletInTwo(
      trackWithItems,
      tracklet,
      rightClickFrameIndex,
      prev,
      next,
      track.id,
    );
    annotations.update((objects) =>
      objects.map((obj) => {
        if (obj.id === track.id && obj.datasetItemType === "video") {
          const { boxes, keypoints } = mapSplittedTrackToObject(trackWithItems, track);
          return { ...obj, track: trackWithItems, boxes, keypoints };
        }
        return obj;
      }),
    );
    track.track = trackWithItems;
    canSave.set(true);
  };

  const onDeleteTrackletClick = (tracklet: TrackletWithItems) => {
    annotations.update((objects) => deleteTracklet(objects, track.id, tracklet));
    updateTracks();
    canSave.set(true);
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

  // const updateTracks = () => {
  //   trackWithItems = [];
  //   for (const tracklet of track.track) {
  //     const boxes = track.boxes
  //       ? track.boxes.filter(
  //           (box) =>
  //             box.view_id === tracklet.view_id &&
  //             box.frame_index >= tracklet.start &&
  //             box.frame_index <= tracklet.end,
  //         )
  //       : [];
  //     const keypoints = track.keypoints
  //       ? track.keypoints.filter(
  //           (kp) =>
  //             kp.view_id === tracklet.view_id &&
  //             kp.frame_index >= tracklet.start &&
  //             kp.frame_index <= tracklet.end,
  //         )
  //       : [];
  //     let items: TrackletItem[] = [];
  //     for (const ann of boxes) {
  //       items.push(getTrackletItem(ann));
  //     }
  //     for (const ann of keypoints) {
  //       const item = getTrackletItem(ann);
  //       if (!items.find((it) => it.frame_index == item.frame_index))
  //         items.push(getTrackletItem(ann));
  //     }
  //     trackWithItems.push({
  //       ...tracklet,
  //       items: items,
  //     });
  //   }
  // };

  // onMount(() => {
  //   updateTracks();
  // });
</script>

{#if track && tracklets}
  <div
    class="flex gap-5 relative h-12 my-auto z-20"
    id={`video-object-${track.id}`}
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
      <!--  //TODO we don't allow adding a point outside of a tracklet right now
            //you can extend tracket to add a point inside, and split if needed
      <ContextMenu.Content>
        <ContextMenu.Item inset on:click={onAddKeyItemClick}>Add a point</ContextMenu.Item>
      </ContextMenu.Content>
      -->
    </ContextMenu.Root>
    {#each tracklets as tracklet (tracklet)}
      <ObjectTracklet
        {tracklet}
        {track}
        {views}
        onAddKeyItemClick={() => onAddKeyItemClick(tracklet)}
        {onContextMenu}
        {onEditKeyItemClick}
        {getTrackletItem}
        onSplitTrackletClick={() => onSplitTrackletClick(tracklet)}
        onDeleteTrackletClick={() => onDeleteTrackletClick(tracklet)}
        {findNeighborItems}
        updateTracks={() => {
          return;
        }}
        {updateView}
        {moveCursorToPosition}
      />
    {/each}
  </div>
{/if}
