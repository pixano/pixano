<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { ToolType } from "$lib/tools";
  import type {
    KeypointAnnotation,
    SequenceFrame,
    TrackletTimelineEntry,
    View,
  } from "$lib/ui";
  import {
    Annotation,
    BaseSchema,
    BBox,
    cn,
    ContextMenu,
    Entity,
    Keypoints,
    Tracklet,
  } from "$lib/ui";

  import { sourcesStore } from "$lib/stores/appStores.svelte";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { sortByFrameIndex } from "$lib/utils/videoUtils";
  import { getPixanoSource, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { deleteEntity } from "$lib/utils/entityMutations";
  import { highlightEntity } from "$lib/utils/highlightOperations";
  import { splitTrackletInTwo, updateView } from "$lib/utils/videoOperations";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";
  import {
    annotations,
    colorScale,
    entities,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "$lib/stores/videoStores.svelte";
  import EntityTracklet from "./EntityTracklet.svelte";

  type MView = Record<string, View | View[]>;

  interface Props {
    track: Entity;
    views: MView;
    onTimeTrackClick: (imageIndex: number) => void;
    bboxes: BBox[];
    keypoints: KeypointAnnotation[];
    resetTool: () => void;
  }

  let {
    track,
    views,
    onTimeTrackClick,
    bboxes,
    keypoints,
    resetTool
  }: Props = $props();

  let objectTimeTrack: HTMLElement = $state();
  let displayName: string = $derived.by(() => {
    const displayFeat = getDefaultDisplayFeat(track);
    return displayFeat ? `${displayFeat} (${track.id})` : track.id;
  });

  let totalWidth = $derived((lastFrameIndex.value / (lastFrameIndex.value + 1)) * 100);
  let color = $derived(colorScale.value[1](track.id));

  let tracklets: Tracklet[] = $derived(
    annotations.value.filter(
      (ann) => ann.is_type(BaseSchema.Tracklet) && ann.data.entity_ref.id === track.id,
    ) as Tracklet[],
  );

  let highlightState: string = $derived.by(() => {
    annotations.value; // track changes
    let state = "all";
    for (const ann of track.ui.childs ?? []) {
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
    onTimeTrackClick(newFrameIndex);
  };

  const onContextMenu = (tracklet: Tracklet | null = null) => {
    if (tracklet && selectedTool.value.type !== ToolType.Fusion) {
      const tracklet_childs_ids = (tracklet.ui.childs ?? []).map((ann) => ann.id);
      annotations.update((oldObjects) =>
        oldObjects.map((ann) => {
          ann.ui.displayControl.highlighted =
            ann.id === tracklet.id || tracklet_childs_ids.includes(ann.id) ? "self" : "none";
          return ann;
        }),
      );
    }
    resetTool();
  };

  const handleTrackContextMenu = (event: MouseEvent) => {
    event.preventDefault();
    onContextMenu();
  };

  const onEditKeyItemClick = (frameIndex: TrackletTimelineEntry["frame_index"], viewname: string) => {
    onTimeTrackClick(frameIndex);
    annotations.update((objects) =>
      objects.map((ann) => {
        const to_highlight =
          ann.data.view_ref.name === viewname &&
          ((!ann.is_type(BaseSchema.Tracklet) &&
            getTopEntity(ann).id === track.id &&
            ann.ui.frame_index === frameIndex) ||
            (ann.is_type(BaseSchema.Tracklet) && ann.data.entity_ref.id === track.id));
        ann.ui.displayControl = {
          ...ann.ui.displayControl,
          highlighted: to_highlight ? "self" : "none",
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
        box.ui.frame_index === currentFrameIndex.value &&
        tracklet.ui.childs.some((ann) => ann.id === box.ui.startRef?.id),
    );
    if (interpolatedBox) {
      const newItemOrig = structuredClone(interpolatedBox);
      const top_entities = interpolatedBox.ui.top_entities; //need to keep it to keep class (lost by structured clone)
      const { ui, ...noUIfieldsBBox } = newItemOrig;
      newItemBBox = new BBox(noUIfieldsBBox);
      //remove startRef now that it's not interpolated, it's a real BBox.
      const { startRef, ...noStartRefUi } = ui; // eslint-disable-line @typescript-eslint/no-unused-vars
      newItemBBox.ui = noStartRefUi;
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
      saveTo("add", newItemBBox);
    }
    const interpolatedKpt = keypoints.find(
      (kpt) =>
        kpt.ui!.frame_index === currentFrameIndex.value &&
        tracklet.ui.childs.some((ann) => ann.id === kpt.ui!.startRef?.id),
    );
    if (interpolatedKpt && interpolatedKpt.ui?.startRef) {
      const keypointsRef = annotations.value.find(
        (ann) => ann.id === interpolatedKpt.ui?.startRef!.id && ann.is_type(BaseSchema.Keypoints),
      ) as Keypoints;
      if (keypointsRef) {
        const newItemOrig = structuredClone(keypointsRef);
        const top_entities = keypointsRef.ui.top_entities; //need to keep it to keep class (lost by structured clone)
        const { ui, ...noUIfieldsBBox } = newItemOrig;
        newItemKpt = new Keypoints(noUIfieldsBBox);
        newItemKpt.ui = ui;
        newItemKpt.ui.top_entities = top_entities;
        newItemKpt.ui.displayControl = interpolatedKpt.ui.displayControl;
        newItemKpt.id = interpolatedKpt.id;
        newItemKpt.ui.frame_index = interpolatedKpt.ui.frame_index;
        newItemKpt.data.view_ref = interpolatedKpt.viewRef!;
        //coords are denormalized: normalize them (??is that so ? to check)
        const current_sf = (views[keypointsRef.data.view_ref.name] as SequenceFrame[])[
          interpolatedKpt.ui.frame_index!
        ];
        const coords = [];
        const states = [];
        for (let vi = 0; vi < interpolatedKpt.graph.vertices.length; vi++) {
          const vertex = interpolatedKpt.graph.vertices[vi];
          coords.push(vertex.x / current_sf.data.width);
          coords.push(vertex.y / current_sf.data.height);
          const meta = interpolatedKpt.vertexMetadata[vi];
          states.push(meta?.state ? meta.state : "visible");
        }
        newItemKpt.data.coords = coords;
        newItemKpt.data.states = states;
        newItemKpt.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
        saveTo("add", newItemKpt);
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
    onEditKeyItemClick(currentFrameIndex.value, tracklet.data.view_ref.name);
  };

  //like findNeighborItems, but "better" (return existing neighbors)
  const findPreviousAndNext = (tracklet: Tracklet): [number, number] => {
    let low = 0;
    let high = tracklet.ui.childs.length - 1;
    let mid;
    let previousItem: Annotation | null = null;
    let nextItem: Annotation | null = null;

    while (low <= high) {
      mid = Math.floor((low + high) / 2);
      if (tracklet.ui.childs[mid].ui.frame_index! <= currentFrameIndex.value) {
        previousItem = tracklet.ui.childs[mid];
        low = mid + 1;
      } else {
        nextItem = tracklet.ui.childs[mid];
        high = mid - 1;
      }
    }
    return [
      previousItem ? previousItem.ui.frame_index! : currentFrameIndex.value,
      nextItem ? nextItem.ui.frame_index! : currentFrameIndex.value + 1,
    ];
  };

  const onSplitTrackletClick = (tracklet: Tracklet) => {
    const [prev, next] = findPreviousAndNext(tracklet);
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

  const findNeighborItems = (tracklet: Tracklet, frameIndex: number): [number, number] => {
    let previous: number = 0;
    let next: number = lastFrameIndex.value;
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
    const newFrameIndex = highlightEntity(track.id, highlightState === "self");
    if (newFrameIndex != currentFrameIndex.value) {
      currentFrameIndex.value = newFrameIndex;
      updateView(currentFrameIndex.value);
    }
  };
</script>

{#if track}
  <div style={`width: ${videoControls.value.zoomLevel[0]}%;`}>
    <div
      class={cn("w-fit sticky left-5 my-1 px-1 border-2 rounded-sm", {
        "text-foreground": highlightState !== "none",
        "text-muted-foreground":
          highlightState === "none" && selectedTool.value.type === ToolType.Fusion,
      })}
      style={`
        background: ${
          highlightState === "self"
            ? `${color}8a`
            : highlightState === "none" && selectedTool.value.type === ToolType.Fusion
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
      <span title="{track.table_info.base_schema} ({track.id})">
        {displayName}
      </span>
    </div>
  </div>
  <div
    id={`video-object-${track.id}`}
    class="flex gap-5 relative my-auto z-20 border-2 rounded-sm"
    style={`
      width: ${videoControls.value.zoomLevel[0]}%;
      height: ${Object.keys(views).length * 10}px;
      background: ${
        highlightState === "self"
          ? `${color}8a`
          : highlightState === "none" && selectedTool.value.type === ToolType.Fusion
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
      <EntityTracklet
        {tracklet}
        trackId={track.id}
        {views}
        onAddKeyItemClick={() => onAddKeyItemClick(tracklet)}
        {onContextMenu}
        {onEditKeyItemClick}
        onSplitTrackletClick={() => onSplitTrackletClick(tracklet)}
        onDeleteTrackletClick={() => deleteEntity(track, tracklet)}
        {findNeighborItems}
        {moveCursorToPosition}
        {resetTool}
      />
    {/each}
  </div>
{/if}
