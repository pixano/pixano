<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ToolType } from "@pixano/canvas2d/src/tools";
  import type {
    KeypointsTemplate,
    SaveItem,
    SequenceFrame,
    TrackletItem,
    View,
  } from "@pixano/core";
  import {
    Annotation,
    BaseSchema,
    BBox,
    ContextMenu,
    Entity,
    Keypoints,
    Track,
    Tracklet,
  } from "@pixano/core";

  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    addOrUpdateSaveItem,
    getPixanoSource,
    getTopEntity,
    highlightObject,
  } from "../../lib/api/objectsApi";
  import { sortByFrameIndex, splitTrackletInTwo, updateView } from "../../lib/api/videoApi";
  import {
    annotations,
    colorScale,
    entities,
    saveData,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import ObjectTracklet from "./ObjectTracklet.svelte";

  type MView = Record<string, View | View[]>;

  export let track: Track;
  export let views: MView;
  export let onTimeTrackClick: (imageIndex: number) => void;
  export let bboxes: BBox[];
  export let keypoints: KeypointsTemplate[];
  export let resetTool: () => void;

  let rightClickFrameIndex: number;
  let objectTimeTrack: HTMLElement;
  let tracklets: Tracklet[];
  let isHighlighted: boolean = false;

  $: totalWidth = ($lastFrameIndex / ($lastFrameIndex + 1)) * 100;
  $: color = $colorScale[1](track.id);

  $: if (track) {
    tracklets = $annotations.filter(
      (ann) => ann.is_type(BaseSchema.Tracklet) && ann.data.entity_ref.id === track.id,
    ) as Tracklet[];
  }

  annotations.subscribe(() => {
    isHighlighted = track.ui.childs?.some((ann) => ann.ui.highlighted === "self") || false;
  });

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
    resetTool();
  };

  const onEditKeyItemClick = (frameIndex: TrackletItem["frame_index"]) => {
    onTimeTrackClick(frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex);
    annotations.update((objects) =>
      objects.map((ann) => {
        const to_highlight =
          (!ann.is_type(BaseSchema.Tracklet) &&
            getTopEntity(ann).id === track.id &&
            ann.ui.frame_index === frameIndex) ||
          (ann.is_type(BaseSchema.Tracklet) && ann.id === track.id);
        ann.ui.highlighted = to_highlight ? "self" : "none";
        ann.ui.displayControl = {
          ...ann.ui.displayControl,
          editing: to_highlight,
        };
        return ann;
      }),
    );
  };

  const onAddKeyItemClick = (tracklet: Tracklet) => {
    let newItemBBox: BBox | undefined = undefined;
    let newItemKpt: Keypoints | undefined = undefined;
    const pixSource = getPixanoSource(sourcesStore);
    //an interpolated obj should exist: use it
    const interpolatedBox = bboxes.find(
      (box) =>
        box.ui.frame_index === rightClickFrameIndex &&
        tracklet.ui.childs.some((ann) => ann.id === box.ui.startRef?.id),
    );
    if (interpolatedBox) {
      const newItemOrig = structuredClone(interpolatedBox);
      const top_entities = interpolatedBox.ui.top_entities; //need to keep it to keep class (lost by structured clone)
      const { ui, ...noUIfieldsBBox } = newItemOrig;
      newItemBBox = new BBox(noUIfieldsBBox);
      newItemBBox.ui = ui;
      newItemBBox.ui.top_entities = top_entities;
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
      newItemBBox.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
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
        (ann) => ann.id === interpolatedKpt.ui!.startRef!.id && ann.is_type(BaseSchema.Keypoints),
      ) as Keypoints;
      if (keypointsRef) {
        const newItemOrig = structuredClone(keypointsRef);
        const top_entities = keypointsRef.ui.top_entities; //need to keep it to keep class (lost by structured clone)
        const { ui, ...noUIfieldsBBox } = newItemOrig;
        newItemKpt = new Keypoints(noUIfieldsBBox);
        newItemKpt.ui = ui;
        newItemKpt.ui.top_entities = top_entities;
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
        newItemKpt.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
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
          if (obj.is_type(BaseSchema.Tracklet) && obj.id === tracklet.id) {
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
    let entitiesToDelete: Entity[] = [];
    entities.update((objects) =>
      objects
        .map((entity) => {
          if (entity.is_track && entity.id === track.id) {
            entity.ui.childs = entity.ui.childs?.filter(
              (ann) => !childs_ids.includes(ann.id) && ann.id !== tracklet.id,
            );
          }
          if (entity.ui.childs?.length == 0) {
            entitiesToDelete.push(entity);
          }
          return entity;
        })
        .filter((entity) => !entitiesToDelete.includes(entity)),
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
    entitiesToDelete.forEach((entityToDelete) => {
      const save_del_entity: SaveItem = {
        change_type: "delete",
        object: entityToDelete,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_del_entity));
    });
  };

  const findNeighborItems = (tracklet: Tracklet, frameIndex: number): [number, number] => {
    let previous: number = 0;
    let next: number = $lastFrameIndex;
    for (const subtracklet of tracklets) {
      if (subtracklet.data.view_ref.name === tracklet.data.view_ref.name) {
        for (const child of subtracklet.ui.childs) {
          if (child.ui.frame_index! < frameIndex && child.ui.frame_index! > previous) {
            previous = child.ui.frame_index!;
          } else if (child.ui.frame_index! > frameIndex && child.ui.frame_index! < next) {
            next = child.ui.frame_index!;
          }
        }
      }
    }
    return [previous, next];
  };

  const onColoredDotClick = () => {
    if ($selectedTool.type === ToolType.Fusion) return;
    const newFrameIndex = highlightObject(track.id, isHighlighted);
    if (newFrameIndex != $currentFrameIndex) {
      currentFrameIndex.set(newFrameIndex);
      updateView($currentFrameIndex);
    }
  };
</script>

{#if track && tracklets}
  <div style={`width: ${$videoControls.zoomLevel[0]}%;`}>
    <div class="w-fit sticky left-5 m-1 px-1" style={`background: ${color}1a;`}>
      <button
        class="rounded-full border w-3 h-3"
        style="background:{color}"
        title="Highlight object"
        on:click={onColoredDotClick}
      />
      <span class="">{track.data.name} ({track.id})</span>
    </div>
  </div>
  <div
    id={`video-object-${track.id}`}
    class="flex gap-5 relative my-auto z-20 border-2"
    style={`
      width: ${$videoControls.zoomLevel[0]}%;
      height: ${Object.keys(views).length * 10}px;
      background: ${color}1a;
      border-color:${isHighlighted ? color : "transparent"}
    `}
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
        trackId={track.id}
        {views}
        onAddKeyItemClick={() => onAddKeyItemClick(tracklet)}
        {onContextMenu}
        {onEditKeyItemClick}
        onSplitTrackletClick={() => onSplitTrackletClick(tracklet)}
        onDeleteTrackletClick={() => onDeleteTrackletClick(tracklet)}
        {findNeighborItems}
        {moveCursorToPosition}
        {resetTool}
      />
    {/each}
  </div>
{/if}
