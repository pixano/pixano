<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import * as ort from "onnxruntime-web";

  import { Canvas2D } from "@pixano/canvas2d";
  import { ToolType } from "@pixano/canvas2d/src/tools";
  import {
    Annotation,
    BaseSchema,
    BBox,
    DatasetItem,
    Entity,
    Keypoints,
    SaveShapeType,
    SequenceFrame,
    Track,
    Tracklet,
    type EditShape,
    type HTMLImage,
    type ImagesPerView,
    type KeypointsTemplate,
    type SaveItem,
  } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { onMount } from "svelte";
  import { derived } from "svelte/store";
  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    addOrUpdateSaveItem,
    getPixanoSource,
    getTopEntity,
    updateExistingObject,
  } from "../../lib/api/objectsApi";
  import { boxLinearInterpolation, keypointsLinearInterpolation } from "../../lib/api/videoApi";
  import { templates } from "../../lib/settings/keyPointsTemplates";
  import {
    annotations,
    merges,
    colorScale,
    entities,
    imageSmoothing,
    itemBboxes,
    itemKeypoints,
    itemMasks,
    newShape,
    saveData,
    selectedKeypointsTemplate,
    selectedTool,
    tracklets,
    views,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import { string } from "zod";

  export let selectedItem: DatasetItem;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  let embeddings: Record<string, ort.Tensor> = {};

  // buffer
  const ratioOfBackwardBuffer = 0.1;
  const bufferSize = 200;
  let previousCount: number = 0;
  let nextCount: number = 0;
  let timerId: ReturnType<typeof setTimeout>;

  $: {
    if (selectedItem) {
      currentFrameIndex.set(0);
    }
  }

  let tracks: Track[] = [];
  entities.subscribe((entities) => {
    tracks = entities.filter((entity) => entity.is_track);
  });

  const current_itemBBoxes = derived(
    [itemBboxes, currentFrameIndex, tracklets],
    ([$itemBboxes, $currentFrameIndex, $tracklets]) => {
      const current_bboxes_and_interpolated: BBox[] = [];
      const current_tracklets = $tracklets.filter(
        (tracklet) =>
          tracklet.data.start_timestep <= $currentFrameIndex &&
          tracklet.data.end_timestep >= $currentFrameIndex,
      );
      for (const tracklet of current_tracklets) {
        const bbox_childs_ids = new Set(
          tracklet.ui.childs.filter((ann) => ann.is_type(BaseSchema.BBox)).map((bbox) => bbox.id),
        );
        const bbox_childs = $itemBboxes.filter((bbox) => bbox_childs_ids.has(bbox.id));
        const box = bbox_childs.find((box) => box.ui.frame_index === $currentFrameIndex);
        if (box) current_bboxes_and_interpolated.push(box);
        else if (bbox_childs.length > 1) {
          const sample_bbox = bbox_childs[0];
          const view_id = ($views[sample_bbox.data.view_ref.name] as SequenceFrame[])[
            $currentFrameIndex
          ].id;
          const interpolated_box = boxLinearInterpolation(bbox_childs, $currentFrameIndex, view_id);
          if (interpolated_box) current_bboxes_and_interpolated.push(interpolated_box);
        }
      }
      return current_bboxes_and_interpolated;
    },
  );

  const current_itemKeypoints = derived(
    [itemKeypoints, currentFrameIndex, tracklets],
    ([$itemKeypoints, $currentFrameIndex, $tracklets]) => {
      const current_kpts_and_interpolated: KeypointsTemplate[] = [];
      const current_tracklets = $tracklets.filter(
        (tracklet) =>
          tracklet.data.start_timestep <= $currentFrameIndex &&
          tracklet.data.end_timestep >= $currentFrameIndex,
      );
      for (const tracklet of current_tracklets) {
        const kpt_childs_ids = new Set(
          tracklet.ui.childs
            .filter((ann) => ann.is_type(BaseSchema.Keypoints))
            .map((kpt) => kpt.id),
        );
        const kpt_childs = $itemKeypoints.filter((kpt) => kpt_childs_ids.has(kpt.id));
        const kpt = kpt_childs.find((kpt) => kpt.ui!.frame_index === $currentFrameIndex);
        if (kpt) current_kpts_and_interpolated.push(kpt);
        else if (kpt_childs.length > 1) {
          const sample_kpt = kpt_childs[0];
          const view_id = ($views[sample_kpt.viewRef!.name] as SequenceFrame[])[$currentFrameIndex]
            .id;
          const interpolated_kpt = keypointsLinearInterpolation(
            kpt_childs,
            $currentFrameIndex,
            view_id,
          );
          if (interpolated_kpt) current_kpts_and_interpolated.push(interpolated_kpt);
        }
      }
      return current_kpts_and_interpolated;
    },
  );

  let inspectorMaxHeight = 250;
  let expanding = false;

  let imagesPerView: ImagesPerView = {};
  const imagesPerViewBuffer: Record<string, HTMLImage[]> = {};

  let imagesFilesUrlsByFrame: Record<string, { id: string; url: string } | undefined>[] = [];

  let isLoaded = false;

  function preloadViewsImage(index: number) {
    Object.entries(imagesFilesUrlsByFrame[index]).map(([viewKey, im_ref]) => {
      if (im_ref && !imagesPerViewBuffer[viewKey][index]) {
        void new Promise<void>((resolve, reject) => {
          const img = new Image();
          img.src = `/${im_ref.url}`;
          img.onload = () => {
            imagesPerViewBuffer[viewKey][index] = {
              id: im_ref.id,
              element: img,
            } as HTMLImage;
            // console.log(
            //   `Image ${im_ref.id} for ${viewKey} loaded and added to buffer at index ${index}.`,
            // );
            resolve();
          };
          img.onerror = () => {
            console.warn(`Failed to load image: ${im_ref.url}`);
            reject(new Error(`Failed to load image: ${im_ref.url}`));
          };
        });
      }
    });
  }

  function preloadImagesProgressively(currentIndex: number = 0) {
    const previous: number[] = [];
    const next: number[] = [];

    const num_frames = $lastFrameIndex + 1;
    // previous (inverted and circular)
    for (let i = 1; i <= previousCount; i++) {
      previous.push((currentIndex - i + num_frames) % num_frames);
    }
    // next (inculing current, circular)
    for (let i = 0; i < nextCount; i++) {
      next.push((currentIndex + i) % num_frames);
    }
    const includedIndices = new Set([...previous, ...next]);
    const excludedIndices = Array.from({ length: num_frames }, (_, i) => i).filter(
      (index) => !includedIndices.has(index),
    );

    clearTimeout(timerId); // reinit timer on each update
    timerId = setTimeout(() => {
      for (const i of next) {
        preloadViewsImage(i);
      }
      for (const i of previous) {
        preloadViewsImage(i);
      }
    }, 20); // timeout to spare bandwith (cancel outdated updates)

    //delete buffered images out of currentIndex window (currentIndex -10 : currentIndex + 30)
    Object.keys(imagesPerViewBuffer).forEach((viewKey) => {
      for (const i of excludedIndices) {
        if (i in imagesPerViewBuffer[viewKey]) {
          delete imagesPerViewBuffer[viewKey][i];
        }
      }
    });
  }

  onMount(() => {
    const longestView = Math.max(
      ...Object.values(selectedItem.views).map((view) => (view as SequenceFrame[]).length),
    );
    //build imagesFilesUrlByFrame
    imagesFilesUrlsByFrame = Array.from({ length: longestView }).map((_, i) => {
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
      imagesPerViewBuffer[viewKey] = [];
    }

    const n_view = Object.keys(imagesPerViewBuffer).length;
    previousCount = Math.round((ratioOfBackwardBuffer * bufferSize) / n_view);
    nextCount = Math.round(((1 - ratioOfBackwardBuffer) * bufferSize) / n_view);

    isLoaded = true;

    lastFrameIndex.set(longestView - 1);
    updateView(0);
  });

  const updateView = (imageIndex: number) => {
    preloadImagesProgressively(imageIndex);
    Object.entries(imagesFilesUrlsByFrame[imageIndex]).forEach(([key, im_ref]) => {
      if (
        key in imagesPerViewBuffer &&
        imagesPerViewBuffer[key][imageIndex] &&
        imagesPerViewBuffer[key][imageIndex].element.complete
      ) {
        imagesPerView = {
          ...imagesPerView,
          [key]: [...(imagesPerView[key] || []), imagesPerViewBuffer[key][imageIndex]].slice(-2),
        };
      } else {
        if (im_ref) {
          const image = new Image();
          const src = `/${im_ref.url}`;
          if (!src) return;
          image.src = src;
          //NOTE double image, avoid flashing by "swapping" with previous image
          imagesPerView = {
            ...imagesPerView,
            [key]: [...(imagesPerView[key] || []), { id: im_ref.id, element: image }].slice(-2),
          };
        } else {
          //console.warn("Media not present")
        }
      }
    });
  };

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
        const top_ent = getTopEntity(ann, $entities);
        if (forbids.map((ent) => ent.id).includes(top_ent.id)) ann.ui.highlighted = "none";
        else if (!to_fuse.map((ent) => ent.id).includes(top_ent.id)) ann.ui.highlighted = "all";
        return ann;
      }),
    );
  };

  const merge = (clicked_ann: Annotation) => {
    if ($selectedTool.type === ToolType.Fusion) {
      const top_entity = getTopEntity(clicked_ann, $entities);
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
              ann.ui.highlighted = "self";
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
              ann.ui.highlighted = "all";
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
      newShape.set({ status: "none" });
    } else {
      annotations.update((objects) => updateExistingObject(objects, shape));
    }
  };

  $: {
    if ($newShape.status === "editing") {
      if ($selectedTool.type !== ToolType.Fusion) {
        updateOrCreateShape($newShape);
      }
    }
  }

  const startExpand = () => {
    expanding = true;
  };

  const stopExpand = () => {
    expanding = false;
  };

  const expand = (e: MouseEvent) => {
    if (expanding) {
      inspectorMaxHeight = document.body.scrollHeight - e.pageY;
    }
  };
</script>

<section
  class="pl-4 h-full w-full flex flex-col"
  on:mouseup={stopExpand}
  on:mousemove={expand}
  role="tab"
  tabindex="0"
>
  {#if isLoaded && $current_itemBBoxes && $current_itemKeypoints && $itemMasks}
    <div class="overflow-hidden grow">
      <Canvas2D
        selectedItemId={selectedItem.item.id}
        {imagesPerView}
        colorScale={$colorScale[1]}
        bboxes={$current_itemBBoxes}
        masks={$itemMasks}
        keypoints={$current_itemKeypoints}
        selectedKeypointTemplate={templates.find(
          (t) => t.template_id === $selectedKeypointsTemplate,
        )}
        canvasSize={inspectorMaxHeight}
        {embeddings}
        isVideo={true}
        imageSmoothing={$imageSmoothing}
        bind:selectedTool={$selectedTool}
        bind:currentAnn
        bind:newShape={$newShape}
        {merge}
      />
    </div>
    <button class="h-1 bg-primary-light cursor-row-resize w-full" on:mousedown={startExpand} />
    <div
      class="h-full grow max-h-[25%] overflow-hidden"
      style={`max-height: ${inspectorMaxHeight}px`}
    >
      <VideoInspector
        bind:tracks
        {updateView}
        bboxes={$current_itemBBoxes}
        keypoints={$current_itemKeypoints}
      />
    </div>
  {/if}
</section>
