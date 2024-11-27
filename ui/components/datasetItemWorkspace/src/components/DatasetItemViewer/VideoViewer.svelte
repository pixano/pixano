<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import * as ort from "onnxruntime-web";

  import {
    DatasetItem,
    Annotation,
    BBox,
    Keypoints,
    Track,
    SequenceFrame,
    type EditShape,
    type KeypointsTemplate,
    type ImagesPerView,
    type HTMLImage,
    type SaveItem,
  } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import {
    itemBboxes,
    itemKeypoints,
    itemMasks,
    tracklets,
    entities,
    annotations,
    views,
    newShape,
    selectedTool,
    colorScale,
    selectedKeypointsTemplate,
    imageSmoothing,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { lastFrameIndex, currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import { onMount } from "svelte";
  import { derived } from "svelte/store";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import {
    updateExistingObject,
    addOrUpdateSaveItem,
    getPixanoSource,
  } from "../../lib/api/objectsApi";
  import { boxLinearInterpolation, keypointsLinearInterpolation } from "../../lib/api/videoApi";
  import { templates } from "../../lib/settings/keyPointsTemplates";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

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
          tracklet.ui.childs.filter((ann) => ann.is_bbox).map((bbox) => bbox.id),
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
          tracklet.ui.childs.filter((ann) => ann.is_keypoints).map((kpt) => kpt.id),
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

    const previousCount = 5;
    const nextCount = 50;
    const num_frames = $lastFrameIndex + 1;
    // previous (inverted and circular)
    for (let i = 1; i <= previousCount; i++) {
      previous.push((currentIndex - i + num_frames) % num_frames);
    }
    // next (inculing current, circular)
    for (let i = 0; i < nextCount; i++) {
      next.push((currentIndex + i) % num_frames);
    }
    for (const i of next) {
      preloadViewsImage(i);
    }
    for (const i of previous) {
      preloadViewsImage(i);
    }
    //delete buffered images out of currentIndex window (currentIndex -10 : currentIndex + 30)
    const includedIndices = new Set([...previous, ...next]);
    const excludedIndices = Array.from({ length: num_frames }, (_, i) => i).filter(
      (index) => !includedIndices.has(index),
    );
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
      if (update_ann.is_bbox && shape.type === "bbox") {
        (update_ann as BBox).data.coords = shape.coords;
      } else if (update_ann.is_keypoints && shape.type === "keypoints") {
        const coords = [];
        const states = [];
        for (const vertex of shape.vertices) {
          coords.push(vertex.x);
          coords.push(vertex.y);
          states.push(vertex.features.state ? vertex.features.state : "visible");
        }
        (update_ann as Keypoints).data.coords = coords;
        (update_ann as Keypoints).data.states = states;
      } else if (update_ann.is_mask) {
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
      if (shape.type === "bbox") {
        const interpolated_box = $current_itemBBoxes.find((box) => box.id === shape.shapeId);
        if (interpolated_box && "startRef" in interpolated_box) {
          const newBBox = structuredClone(interpolated_box.startRef as BBox);
          newBBox.id = shape.shapeId;
          newBBox.data.coords = shape.coords;
          newBBox.data.view_ref = shape.viewRef;
          newBBox.ui.frame_index = currentFrame;
          newBBox.updated_at = new Date(Date.now()).toISOString();
          newAnn = newBBox;
        }
      } else if (shape.type === "keypoints") {
        const interpolated_kpt = $current_itemKeypoints.find((kpt) => kpt.id === shape.shapeId);
        if (interpolated_kpt && "startRef" in interpolated_kpt) {
          const keypointRef = annotations.find(
            (ann) => ann.is_keypoints && ann.id === interpolated_kpt.ui!.startRef?.id,
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
            newKpt.updated_at = new Date(Date.now()).toISOString();
            newAnn = newKpt;
          }
        }
      } else if (shape.type === "mask") {
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
    if (shape.type === "bbox" || shape.type === "keypoints") {
      let { objects, save_data } = editKeyItemInTracklet($annotations, shape, $currentFrameIndex);
      annotations.set(objects);
      if (save_data) saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_data));
      newShape.set({ status: "none" });
    } else {
      annotations.update((objects) => updateExistingObject(objects, shape));
    }
  };

  $: {
    const shape = $newShape;
    if (shape.status === "editing") {
      updateOrCreateShape(shape);
    }
  }

  //$: selectedTool.set($selectedTool);

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
