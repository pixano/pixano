<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu, Annotation, Entity, BBox, Keypoints, Track, Tracklet } from "@pixano/core";
  import type {
    TrackletItem,
    MView,
    SaveItem,
    SequenceFrame,
    KeypointsTemplate,
  } from "@pixano/core";
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
  import { addOrUpdateSaveItem, getTopEntity } from "../../lib/api/objectsApi";

  export let track: Track;
  export let views: MView;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let bboxes: BBox[];
  export let keypoints: KeypointsTemplate[];

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
    rightClickFrameIndex = Math.round(rightClickFrame * ($lastFrameIndex + 1));
    onTimeTrackClick(rightClickFrameIndex);
  };

  const onContextMenu = (event: MouseEvent, tracklet: Tracklet | null = null) => {
    if (tracklet) {
      const tracklet_childs_ids = tracklet.ui.childs.map((ann) => ann.id);
      annotations.update((oldObjects) =>
        oldObjects.map((ann) => {
          ann.ui.highlighted =
            ann.id === tracklet.id || tracklet_childs_ids.includes(ann.id) ? "self" : "none";
          return ann;
        }),
      );
    }
    moveCursorToPosition(event.clientX);
    selectedTool.set(panTool);
  };

  const onEditKeyItemClick = (frameIndex: TrackletItem["frame_index"]) => {
    onTimeTrackClick(frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex);
    annotations.update((objects) =>
      objects.map((ann) => {
        const to_highlight =
          (!ann.is_tracklet &&
            getTopEntity(ann, $entities).id === track.id &&
            ann.ui.frame_index === frameIndex) ||
          (ann.is_tracklet && ann.id === track.id);
        ann.ui.highlighted = to_highlight ? "self" : "none";
        ann.ui.displayControl = {
          ...ann.ui.displayControl,
          editing: to_highlight,
        };
        return ann;
      }),
    );
  };

  const onAddKeyItemClick = (tracklet: Tracklet | MouseEvent) => {
    if (tracklet instanceof MouseEvent) {
      //MouseEvent, need to determine view_id
      //TODO
      confirm("Adding a key point outside of a tracklet is forbidden for now");
    } else {
      let newItemBBox: BBox | undefined = undefined;
      let newItemKpt: Keypoints | undefined = undefined;
      //an interpolated obj should exist: use it
      const interpolatedBox = bboxes.find(
        (box) =>
          box.ui.frame_index === rightClickFrameIndex &&
          tracklet.ui.childs.some((ann) => ann.id === box.ui.startRef?.id),
      );
      if (interpolatedBox) {
        const newItemOrig = structuredClone(interpolatedBox);
        const { ui, ...noUIfieldsBBox } = newItemOrig;
        newItemBBox = new BBox(noUIfieldsBBox);
        newItemBBox.ui = ui;
        //coords are denormalized: normalize them
        const current_sf = (views[newItemBBox.data.view_ref.name] as SequenceFrame[])[
          newItemBBox.ui.frame_index!
        ];
        const [x, y, w, h] = newItemBBox.data.coords;
        newItemBBox.data.coords = [
          x / current_sf.data.width,
          y / current_sf.data.height,
          w / current_sf.data.width,
          h / current_sf.data.height,
        ];
        const save_new_item: SaveItem = {
          change_type: "add",
          object: newItemBBox,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_new_item));
      }
      const interpolatedKpt = keypoints.find(
        (kpt) =>
          kpt.ui!.frame_index === rightClickFrameIndex &&
          tracklet.ui.childs.some((ann) => ann.id === kpt.ui!.startRef?.id),
      );
      if (interpolatedKpt && interpolatedKpt.ui!.startRef) {
        const keypointsRef = $annotations.find(
          (ann) => ann.id === interpolatedKpt.ui!.startRef!.id && ann.is_keypoints,
        ) as Keypoints;
        if (keypointsRef) {
          const newItemOrig = structuredClone(keypointsRef);
          const { ui, ...noUIfieldsBBox } = newItemOrig;
          newItemKpt = new Keypoints(noUIfieldsBBox);
          newItemKpt.ui = ui;
          if (interpolatedKpt.ui!.displayControl)
            newItemKpt.ui.displayControl = interpolatedKpt.ui!.displayControl;
          if (interpolatedKpt.ui!.highlighted)
            newItemKpt.ui.highlighted = interpolatedKpt.ui!.highlighted;
          if (interpolatedKpt.ui!.displayControl)
            newItemKpt.ui.displayControl = {
              hidden: interpolatedKpt.ui!.displayControl.hidden,
              editing: interpolatedKpt.ui!.displayControl.editing, //TODO maybe we should just set it to true ?
            };
          newItemKpt.id = interpolatedKpt.id;
          newItemKpt.ui.frame_index = interpolatedKpt.ui!.frame_index;
          newItemKpt.data.view_ref = interpolatedKpt.viewRef!;
          //coords are denormalized: normalize them (??is that so ? to check)
          const current_sf = (views[keypointsRef.data.view_ref.name] as SequenceFrame[])[
            interpolatedKpt.ui!.frame_index!
          ];
          const coords = [];
          const states = [];
          for (const vertex of interpolatedKpt.vertices) {
            coords.push(vertex.x / current_sf.data.width);
            coords.push(vertex.y / current_sf.data.height);
            states.push(vertex.features.state ? vertex.features.state : "visible");
          }
          newItemKpt.data.coords = coords;
          newItemKpt.data.states = states;

          const save_new_item: SaveItem = {
            change_type: "add",
            object: newItemKpt,
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_new_item));
        }
      }
      //TODO no interpolated Mask yet

      if (newItemBBox || newItemKpt) {
        annotations.update((objects) => {
          objects.map((obj) => {
            if (obj.is_tracklet && obj.id === tracklet.id) {
              const obj_tracket = obj as Tracklet;
              // add item in childs
              if (newItemBBox) obj_tracket.ui.childs = [...obj_tracket.ui.childs, newItemBBox];
              if (newItemKpt) obj_tracket.ui.childs = [...obj_tracket.ui.childs, newItemKpt];
              obj_tracket.ui.childs?.sort((a, b) => sortByFrameIndex(a, b));
            }
            return obj;
          });
          if (newItemBBox) objects.push(newItemBBox);
          if (newItemKpt) objects.push(newItemKpt);
          objects.sort((a, b) => sortByFrameIndex(a, b));
          return objects;
        });
        entities.update((objects) =>
          objects.map((entity) => {
            if (entity.id === tracklet.data.entity_ref.id) {
              if (newItemBBox) entity.ui.childs = [...entity.ui.childs!, newItemBBox];
              if (newItemKpt) entity.ui.childs = [...entity.ui.childs!, newItemKpt];
              entity.ui.childs?.sort((a, b) => sortByFrameIndex(a, b));
            }
            return entity;
          }),
        );
      }
      onEditKeyItemClick(rightClickFrameIndex);
    }
  };

  //like findNeighborItems, but "better" (return existing neighbors)
  const findPreviousAndNext = (tracklet: Tracklet, targetIndex: number): [number, number] => {
    let low = 0;
    let high = tracklet.ui.childs.length - 1;
    let mid;
    let previousItem: Annotation | null = null;
    let nextItem: Annotation | null = null;

    while (low <= high) {
      mid = Math.floor((low + high) / 2);
      if (tracklet.ui.childs[mid].ui.frame_index! <= targetIndex) {
        previousItem = tracklet.ui.childs[mid];
        low = mid + 1;
      } else {
        nextItem = tracklet.ui.childs[mid];
        high = mid - 1;
      }
    }
    return [
      previousItem ? previousItem.ui.frame_index! : targetIndex,
      nextItem ? nextItem.ui.frame_index! : targetIndex + 1,
    ];
  };

  const onSplitTrackletClick = (tracklet: Tracklet) => {
    const [prev, next] = findPreviousAndNext(tracklet, rightClickFrameIndex);
    const newOnRight = splitTrackletInTwo(tracklet, prev, next);
    //add Entity child
    entities.update((objects) =>
      objects.map((entity) => {
        if (entity.is_track && entity.id === track.id) {
          entity.ui.childs = [...entity.ui.childs!, newOnRight];
          entity.ui.childs?.sort((a, b) => sortByFrameIndex(a, b));
        }
        return entity;
      }),
    );
    annotations.update((objects) => objects.concat(newOnRight));
  };

  const onDeleteTrackletClick = (tracklet: Tracklet) => {
    const childs_ids = tracklet.ui.childs?.map((ann) => ann.id);
    let to_del_entity: Entity | null = null;
    entities.update((objects) =>
      objects.map((entity) => {
        if (entity.is_track && entity.id === track.id)
          entity.ui.childs = entity.ui.childs?.filter(
            (ann) => !childs_ids.includes(ann.id) && ann.id !== tracklet.id,
          );
        if (entity.ui.childs?.length == 0) {
          to_del_entity = entity;
        }
        return entity;
      }),
    );
    annotations.update((anns) =>
      anns.filter((ann) => !childs_ids.includes(ann.id) && ann.id !== tracklet.id),
    );
    tracklet.ui.childs?.forEach((ann) => {
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
      for (const child of subtracklet.ui.childs) {
        if (child.ui.frame_index! < frameIndex) {
          previous = child.ui.frame_index!;
        } else if (child.ui.frame_index! > frameIndex) {
          if (!nextChild || child.ui.frame_index! < nextChild.ui.frame_index!) {
            nextChild = child;
            next = nextChild.ui.frame_index!;
          }
        }
      }
    }
    return [previous, next];
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
        onSplitTrackletClick={() => onSplitTrackletClick(tracklet)}
        onDeleteTrackletClick={() => onDeleteTrackletClick(tracklet)}
        {findNeighborItems}
        {moveCursorToPosition}
      />
    {/each}
  </div>
{/if}
