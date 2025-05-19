<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { Canvas2D } from "@pixano/canvas2d";
  import { ToolType } from "@pixano/canvas2d/src/tools";
  import {
    Annotation,
    BaseSchema,
    BBox,
    DatasetItem,
    Entity,
    Keypoints,
    Mask,
    SaveShapeType,
    SequenceFrame,
    Tracklet,
    type Box,
    type EditShape,
    type LabeledClick,
    type Reference,
    type SaveItem,
  } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    addOrUpdateSaveItem,
    getPixanoSource,
    getTopEntity,
    scrollIntoView,
    updateExistingObject,
  } from "../../lib/api/objectsApi";
  import { setBufferSpecs, updateView } from "../../lib/api/videoApi";
  import { templates } from "../../lib/settings/keyPointsTemplates";
  import {
    annotations,
    colorScale,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    embeddings,
    entities,
    imageSmoothing,
    itemMasks,
    merges,
    newShape,
    saveData,
    selectedKeypointsTemplate,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    currentFrameIndex,
    imagesFilesUrlsByFrame,
    imagesPerView,
    imagesPerViewBuffer,
    lastFrameIndex,
  } from "../../lib/stores/videoViewerStores";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";

  export let selectedItem: DatasetItem;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let resize: number;
  export let pixanoInferenceSegmentation: (
    viewRef: Reference,
    points: LabeledClick[],
    box: Box,
  ) => Promise<Mask | undefined>;

  $: {
    if (selectedItem) {
      currentFrameIndex.set(0);
    }
  }

  let inspectorMaxHeight = 250;
  let expanding = false;
  let isLoaded = false;

  onMount(() => {
    const longestView = Math.max(
      ...Object.values(selectedItem.views).map((view) => (view as SequenceFrame[]).length),
    );
    //build imagesFilesUrlByFrame
    $imagesFilesUrlsByFrame = Array.from({ length: longestView }).map((_, i) => {
      return Object.entries(selectedItem.views).reduce(
        (acc, [key, value]) => {
          const viewFrames = value as SequenceFrame[];
          acc[key] = viewFrames[i]
            ? { id: viewFrames[i].id, url: viewFrames[i].data.url }
            : undefined;
          return acc;
        },
        {} as Record<string, { id: string; url: string } | undefined>,
      );
    });
    // Initialize the buffer structure with arrays for each view
    for (const viewKey in selectedItem.views) {
      $imagesPerViewBuffer[viewKey] = [];
    }

    setBufferSpecs();

    isLoaded = true;

    lastFrameIndex.set(longestView - 1);
    updateView(0);
  });

  function mergeFusionRangesByView(to_fuse: Entity[]): Record<string, [number, number][]> {
    //build combined tracklet ranges for each view of to_fuse entities
    const trackletsByView: Record<string, Tracklet[]> = {};
    to_fuse
      .flatMap((ent) =>
        ent.ui.childs
          ? (ent.ui.childs.filter((ann) => ann.is_type(BaseSchema.Tracklet)) as Tracklet[])
          : [],
      )
      .forEach((tracklet) => {
        if (!(tracklet.data.view_ref.name in trackletsByView))
          trackletsByView[tracklet.data.view_ref.name] = [];
        trackletsByView[tracklet.data.view_ref.name].push(tracklet);
      });

    const mergedByView: Record<string, [number, number][]> = {};
    Object.entries(trackletsByView).forEach(([view, tracklets]) => {
      mergedByView[view] = [];
      if (tracklets.length > 0) {
        // sort to ease merge
        tracklets.sort((a, b) => a.data.start_timestep - b.data.start_timestep);
        let currentTracklet = { ...tracklets[0] };
        for (let i = 1; i < tracklets.length; i++) {
          const tracklet = tracklets[i];
          if (tracklet.data.start_timestep <= currentTracklet.data.end_timestep) {
            // Merge range if overlap (or touching)
            currentTracklet.data.end_timestep = Math.max(
              currentTracklet.data.end_timestep,
              tracklet.data.end_timestep,
            );
          } else {
            // Add merged range and start a new one
            mergedByView[view].push([
              currentTracklet.data.start_timestep,
              currentTracklet.data.end_timestep,
            ]);
            currentTracklet = { ...tracklet };
          }
        }
        // Add last range
        mergedByView[view].push([
          currentTracklet.data.start_timestep,
          currentTracklet.data.end_timestep,
        ]);
      }
    });
    return mergedByView;
  }

  function canMergeRangesByView(
    record1: Record<string, [number, number][]>,
    record2: Record<string, [number, number][]>,
  ): boolean {
    // Get all possible views
    const allViews = new Set([...Object.keys(record1), ...Object.keys(record2)]);

    for (const view of allViews) {
      const ranges1 = record1[view] || [];
      const ranges2 = record2[view] || [];

      // sort both ranges on start then end
      const allRanges = [...ranges1, ...ranges2].sort((a, b) =>
        a[0] === b[0] ? a[1] - b[1] : a[0] - b[0],
      );
      // check if ranges overlap or touch
      for (let i = 1; i < allRanges.length; i++) {
        const prev = allRanges[i - 1];
        const curr = allRanges[i];
        if (prev[1] >= curr[0]) {
          return false;
        }
      }
    }
    return true;
  }

  const checkMergeForbids = (to_fuse: Entity[]) => {
    const forbids: Entity[] = $merges.forbids;
    const to_fuse_ranges = mergeFusionRangesByView(to_fuse);
    const others = $entities.filter(
      (ent) => !to_fuse.includes(ent) && ent.data.parent_ref.id === "",
    );
    others.forEach((ent) => {
      const ranges = mergeFusionRangesByView([ent]);
      if (canMergeRangesByView(ranges, to_fuse_ranges)) {
        //remove from forbids (if present)
        if (forbids.includes(ent)) {
          const remove_index = forbids.indexOf(ent, 0);
          forbids.splice(remove_index, 1);
        }
      } else {
        //add to forbids
        if (!forbids.includes(ent)) {
          forbids.push(ent);
        }
      }
    });
    //adapt highlights
    annotations.update((anns) =>
      anns.map((ann) => {
        const top_ent = getTopEntity(ann);
        if (forbids.map((ent) => ent.id).includes(top_ent.id))
          ann.ui.displayControl.highlighted = "none";
        else if (!to_fuse.map((ent) => ent.id).includes(top_ent.id))
          ann.ui.displayControl.highlighted = "all";
        return ann;
      }),
    );
  };

  const merge = (clicked_ann: Annotation) => {
    if ($selectedTool.type === ToolType.Fusion) {
      const top_entity = getTopEntity(clicked_ann);
      //check if top_entity is allowed
      if ($merges.forbids.includes(top_entity)) return;

      if (!$merges.to_fuse.includes(top_entity)) {
        merges.update((assoc) => ({
          to_fuse: [...assoc.to_fuse, top_entity],
          forbids: assoc.forbids,
        }));
        //highlight
        annotations.update((anns) =>
          anns.map((ann) => {
            if (top_entity.ui.childs?.includes(ann) /*&& !ann.is_type(BaseSchema.Tracklet)*/) {
              ann.ui.displayControl.highlighted = "self";
            }
            return ann;
          }),
        );
      } else {
        //already here, then remove it
        merges.update((assoc) => {
          const remove_index = assoc.to_fuse.indexOf(top_entity, 0);
          assoc.to_fuse.splice(remove_index, 1);
          return assoc;
        });
        //unhighlight
        annotations.update((anns) =>
          anns.map((ann) => {
            if (top_entity.ui.childs?.includes(ann) /*&& !ann.is_type(BaseSchema.Tracklet)*/) {
              ann.ui.displayControl.highlighted = "all";
            }
            return ann;
          }),
        );
      }
      checkMergeForbids($merges.to_fuse);
    }
  };

  const editKeyItemInTracklet = (
    annotations: Annotation[],
    shape: EditShape,
    currentFrame: number,
  ): { objects: Annotation[]; save_data: SaveItem } => {
    let saveData: SaveItem;
    let updated_annotations: Annotation[];
    //find corresponding annotation
    const update_ann = annotations.find((ann) => ann.id === shape.shapeId);
    if (update_ann) {
      if (update_ann.is_type(BaseSchema.BBox) && shape.type === SaveShapeType.bbox) {
        (update_ann as BBox).data.coords = shape.coords;
      } else if (
        update_ann.is_type(BaseSchema.Keypoints) &&
        shape.type === SaveShapeType.keypoints
      ) {
        const coords = [];
        const states = [];
        for (const vertex of shape.vertices) {
          coords.push(vertex.x);
          coords.push(vertex.y);
          states.push(vertex.features.state ? vertex.features.state : "visible");
        }
        (update_ann as Keypoints).data.coords = coords;
        (update_ann as Keypoints).data.states = states;
      } else if (update_ann.is_type(BaseSchema.Mask)) {
        console.log("TODO! mask");
        //mask not implemented yet in video
      } else {
        // should not happen
        console.error(
          `ERROR: mismatching types ${shape.type} & ${update_ann.table_info.base_schema}`,
        );
      }
      const pixSource = getPixanoSource(sourcesStore);
      update_ann.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
      //update
      updated_annotations = annotations.map((ann) => (ann.id === update_ann.id ? update_ann : ann));
      saveData = {
        change_type: "update",
        object: update_ann,
      };
    } else {
      //updated an interpolated annotation: create it
      //use start ann of interpolated as base for new ann
      let newAnn: Annotation | undefined = undefined;
      if (shape.type === SaveShapeType.bbox) {
        const interpolated_box = $current_itemBBoxes.find((box) => box.id === shape.shapeId);
        if (interpolated_box && "startRef" in interpolated_box) {
          const newBBox = structuredClone(interpolated_box.startRef as BBox);
          newBBox.id = shape.shapeId;
          newBBox.data.coords = shape.coords;
          newBBox.data.view_ref = shape.viewRef;
          newBBox.ui.frame_index = currentFrame;
          newBBox.updated_at = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
          newAnn = newBBox;
        }
      } else if (shape.type === SaveShapeType.keypoints) {
        const interpolated_kpt = $current_itemKeypoints.find((kpt) => kpt.id === shape.shapeId);
        if (interpolated_kpt && "startRef" in interpolated_kpt) {
          const keypointRef = annotations.find(
            (ann) =>
              ann.is_type(BaseSchema.Keypoints) && ann.id === interpolated_kpt.ui!.startRef?.id,
          ) as Keypoints;
          if (keypointRef) {
            const newKpt = structuredClone(keypointRef);
            const coords = [];
            const states = [];
            for (const vertex of shape.vertices) {
              coords.push(vertex.x);
              coords.push(vertex.y);
              states.push(vertex.features.state ? vertex.features.state : "visible");
            }
            newKpt.id = shape.shapeId;
            newKpt.data.coords = coords;
            newKpt.data.states = states;
            newKpt.data.view_ref = shape.viewRef;
            newKpt.ui.frame_index = currentFrame;
            newKpt.updated_at = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
            newAnn = newKpt;
          }
        }
      } else if (shape.type === SaveShapeType.mask) {
        console.log("TODO! mask");
        //mask not implemented yet in video
      }
      if (!newAnn) {
        //TODO - remove this when mask managed (used mainly to avoid lint warnings)
        throw new Error("Masks are not managed yet in video!");
      }
      //update
      const pixSource = getPixanoSource(sourcesStore);
      newAnn.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
      updated_annotations = [...annotations, newAnn];
      saveData = {
        change_type: "add",
        object: newAnn,
      };
    }
    return {
      objects: updated_annotations,
      save_data: saveData,
    };
  };

  const updateOrCreateShape = (shape: EditShape) => {
    if (shape.type === SaveShapeType.bbox || shape.type === SaveShapeType.keypoints) {
      let { objects, save_data } = editKeyItemInTracklet($annotations, shape, $currentFrameIndex);
      annotations.set(objects);
      if (save_data) saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_data));
    } else {
      annotations.update((objects) => updateExistingObject(objects, shape));
    }
    newShape.set({ status: "none" });
  };

  $: {
    if ($newShape.status === "editing") {
      if ($selectedTool.type !== ToolType.Fusion) {
        updateOrCreateShape($newShape);
      } else {
        if ($newShape.top_entity_id) {
          scrollIntoView($newShape.top_entity_id);
        }
      }
    }
  }

  const expand = (e: MouseEvent) => {
    if (expanding) {
      inspectorMaxHeight = document.body.scrollHeight - e.pageY;
    }
  };
</script>

<section
  class="h-full w-full flex flex-col"
  on:mouseup={() => {
    expanding = false;
  }}
  on:mousemove={expand}
  role="tab"
  tabindex="0"
>
  {#if isLoaded && $current_itemBBoxes && $current_itemKeypoints && $itemMasks}
    <div class="overflow-hidden grow">
      <Canvas2D
        selectedItemId={selectedItem.item.id}
        imagesPerView={$imagesPerView}
        colorScale={$colorScale[1]}
        bboxes={$current_itemBBoxes}
        masks={$current_itemMasks}
        keypoints={$current_itemKeypoints}
        selectedKeypointTemplate={templates.find(
          (t) => t.template_id === $selectedKeypointsTemplate,
        )}
        {pixanoInferenceSegmentation}
        canvasSize={inspectorMaxHeight + resize}
        isVideo={true}
        embeddings={$embeddings}
        imageSmoothing={$imageSmoothing}
        bind:selectedTool={$selectedTool}
        bind:currentAnn
        bind:newShape={$newShape}
        {merge}
      />
    </div>
    <button
      class="h-1 bg-primary-light cursor-row-resize w-full"
      on:mousedown={() => {
        expanding = true;
      }}
    />
    <div
      class="h-full grow max-h-[25%] overflow-hidden"
      style={`max-height: ${inspectorMaxHeight}px`}
    >
      <VideoInspector bboxes={$current_itemBBoxes} keypoints={$current_itemKeypoints} />
    </div>
  {/if}
</section>
