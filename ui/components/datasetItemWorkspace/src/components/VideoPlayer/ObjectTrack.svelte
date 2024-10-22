<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, Annotation, Entity, BBox, Track, Tracklet } from "@pixano/core";
  import type { TrackletItem, MView, SaveItem, SequenceFrame } from "@pixano/core";
  import {
    annotations,
    entities,
    selectedTool,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { sortByFrameIndex, splitTrackletInTwo } from "../../lib/api/videoApi";
  import ObjectTracklet from "./ObjectTracklet.svelte";
  import { panTool } from "../../lib/settings/selectionTools";
  import { highlightCurrentObject, addOrUpdateSaveItem } from "../../lib/api/objectsApi";

  export let track: Track;
  export let views: MView;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let bboxes: BBox[];

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

  const onContextMenu = (event: MouseEvent, tracklet: Tracklet | null = null) => {
    if (tracklet) annotations.update((oldObjects) => highlightCurrentObject(oldObjects, tracklet));
    moveCursorToPosition(event.clientX);
    selectedTool.set(panTool);
  };

  const onEditKeyItemClick = (frameIndex: TrackletItem["frame_index"]) => {
    onTimeTrackClick(frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex);
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

  const onAddKeyItemClick = (tracklet: Tracklet | MouseEvent) => {
    if (tracklet instanceof MouseEvent) {
      //MouseEvent, need to determine view_id
      //TODO
      confirm("Adding a key point outside of a tracklet is forbidden for now");
    } else {
      //an interpolated obj should exist: use it
      //TODO: if keypoints/mask ...
      const interpolatedItem = bboxes.find((box) => box.frame_index === rightClickFrameIndex);
      if (interpolatedItem) {
        console.log("zaz", rightClickFrameIndex, interpolatedItem);
        const newItemOrig = structuredClone(interpolatedItem);
        const {
          datasetItemType,
          displayControl,
          highlighted,
          frame_index,
          review_state,
          opacity,
          visible,
          editing,
          strokeFactor,
          tooltip,
          ...noUIfieldsBBox
        } = newItemOrig;
        if ("startRef" in noUIfieldsBBox) delete noUIfieldsBBox.startRef;
        if ("endRef" in noUIfieldsBBox) delete noUIfieldsBBox.endRef;
        const newItem = new BBox(noUIfieldsBBox);
        newItem.datasetItemType = datasetItemType;
        newItem.displayControl = displayControl;
        newItem.highlighted = highlighted;
        newItem.frame_index = frame_index;
        newItem.review_state = review_state;
        newItem.opacity = opacity;
        newItem.visible = visible;
        newItem.editing = editing;
        newItem.strokeFactor = strokeFactor;
        newItem.tooltip = tooltip;
        //coords are denormalized: normalize them
        const current_sf = (views[newItem.data.view_ref.name] as SequenceFrame[])[
          newItem.frame_index!
        ];
        const [x, y, w, h] = newItem.data.coords;
        newItem.data.coords = [
          x / current_sf.data.width,
          y / current_sf.data.height,
          w / current_sf.data.width,
          h / current_sf.data.height,
        ];

        annotations.update((objects) => {
          objects.map((obj) => {
            if (obj.is_tracklet && obj.id === tracklet.id) {
              // add item in childs
              (obj as Tracklet).childs?.push(newItem);
              (obj as Tracklet).childs?.sort((a, b) => sortByFrameIndex(a, b));
            }
            return obj;
          });
          objects.push(newItem);
          return objects;
        });

        const save_new_item: SaveItem = {
          change_type: "add",
          object: newItem,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_new_item));
      } else {
        console.error("No interpolated BBox found !");
      }
      onEditKeyItemClick(rightClickFrameIndex);
    }
  };

  //like findNeighborItems, but "better" (return existing neighbors)
  const findPreviousAndNext = (tracklet: Tracklet, targetIndex: number): [number, number] => {
    let low = 0;
    let high = tracklet.childs.length - 1;
    let mid;
    let previousItem: Annotation | null = null;
    let nextItem: Annotation | null = null;

    while (low <= high) {
      mid = Math.floor((low + high) / 2);
      if (tracklet.childs[mid].frame_index! <= targetIndex) {
        previousItem = tracklet.childs[mid];
        low = mid + 1;
      } else {
        nextItem = tracklet.childs[mid];
        high = mid - 1;
      }
    }
    return [
      previousItem ? previousItem.frame_index! : targetIndex,
      nextItem ? nextItem.frame_index! : targetIndex + 1,
    ];
  };

  const onSplitTrackletClick = (tracklet: Tracklet) => {
    const [prev, next] = findPreviousAndNext(tracklet, rightClickFrameIndex);
    const { left, right } = splitTrackletInTwo(tracklet, prev, next);
    //add Entity child
    entities.update((objects) =>
      objects.map((entity) => {
        if (entity.is_track && entity.id === track.id) {
          entity.childs?.push(right);
          entity.childs?.sort((a, b) => sortByFrameIndex(a, b));
        }
        return entity;
      }),
    );

    annotations.update((objects) => objects.concat(right));
  };

  const onDeleteTrackletClick = (tracklet: Tracklet) => {
    const childs_ids = tracklet.childs?.map((ann) => ann.id);
    let to_del_entity: Entity | null = null;
    entities.update((objects) =>
      objects.map((entity) => {
        if (entity.is_track && entity.id === track.id)
          entity.childs = entity.childs?.filter(
            (ann) => !childs_ids.includes(ann.id) && ann.id !== tracklet.id,
          );
        if (entity.childs?.length == 0) {
          to_del_entity = entity;
        }
        return entity;
      }),
    );
    annotations.update((anns) =>
      anns.filter((ann) => !childs_ids.includes(ann.id) && ann.id !== tracklet.id),
    );
    tracklet.childs?.forEach((ann) => {
      const save_del_ann: SaveItem = {
        change_type: "delete",
        object: ann,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_del_ann));
    });
    const save_del_tracklet: SaveItem = {
      change_type: "delete",
      object: tracklet,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_del_tracklet));
    if (to_del_entity) {
      const save_del_entity: SaveItem = {
        change_type: "delete",
        object: to_del_entity,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_del_entity));
    }
  };

  const findNeighborItems = (frameIndex: number): [number, number] => {
    let previous: number = 0;
    let nextChild: Annotation | undefined = undefined;
    let next: number = $lastFrameIndex;

    for (const subtracklet of tracklets) {
      for (const child of subtracklet.childs) {
        if (child.frame_index! < frameIndex) {
          previous = child.frame_index!;
        } else if (child.frame_index! > frameIndex) {
          if (!nextChild || child.frame_index! < nextChild.frame_index!) {
            nextChild = child;
            next = nextChild.frame_index!;
          }
        }
      }
    }
    return [previous, next];
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
        {moveCursorToPosition}
      />
    {/each}
  </div>
{/if}
