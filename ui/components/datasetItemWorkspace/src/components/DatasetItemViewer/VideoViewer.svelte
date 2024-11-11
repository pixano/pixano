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
  import { lastFrameIndex, currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import { onMount } from "svelte";
  import { derived } from "svelte/store";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import { updateExistingObject, addOrUpdateSaveItem } from "../../lib/api/objectsApi";
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

  let imagesFilesUrls: Record<string, { id: string; url: string }[]> = Object.entries(
    selectedItem.views,
  ).reduce(
    (acc, [key, value]) => {
      acc[key] = (value as SequenceFrame[]).map((view) => {
        return { id: view.id, url: view.data.url };
      });
      return acc;
    },
    {} as Record<string, { id: string; url: string }[]>,
  );

  let isLoaded = false;

  async function preloadImagesProgressively(
    imagesFilesUrls: Record<string, { id: string; url: string }[]>,
  ) {
    // Initialize the buffer structure with arrays for each view
    for (const [viewKey, frames] of Object.entries(imagesFilesUrls)) {
      imagesPerViewBuffer[viewKey] = new Array<HTMLImage>(frames.length);
    }
    // Create an array of promises for loading images
    const loadPromises = Object.entries(imagesFilesUrls).flatMap(([viewKey, frames]) =>
      frames.map(
        ({ id, url }, index) =>
          new Promise<void>((resolve, reject) => {
            const img = new Image();
            img.src = `/${url}`;
            img.onload = () => {
              imagesPerViewBuffer[viewKey][index] = { id, element: img } as HTMLImage;
              //console.log(`Image ${id} for ${viewKey} loaded and added to buffer at index ${index}.`);
              resolve();
            };
            img.onerror = () => {
              console.warn(`Failed to load image: ${url}`);
              reject(new Error(`Failed to load image: ${url}`));
            };
          }),
      ),
    );
    // Await all images to finish loading, without holding up the buffer population
    await Promise.allSettled(loadPromises);
  }

  onMount(() => {
    Object.entries(imagesFilesUrls).forEach(([key, urls]) => {
      const image = new Image();
      image.src = `/${urls[0].url}`;
      imagesPerView = {
        ...imagesPerView,
        [key]: [{ id: urls[0].id, element: image }],
      };
    });

    isLoaded = true;
    const longestView = Object.values(imagesFilesUrls).reduce(
      (acc, urls) => (urls.length > acc ? urls.length : acc),
      0,
    );
    lastFrameIndex.set(longestView - 1);

    //preload buffer
    preloadImagesProgressively(imagesFilesUrls)
      .then(() => {
        console.log("Progressive loading complete.");
      })
      .catch((error) => {
        console.error("Error during progressive loading:", error);
      });
  });

  const updateView = (imageIndex: number) => {
    Object.entries(imagesFilesUrls).forEach(([key, urls]) => {
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
        const image = new Image();
        const src = `/${urls[imageIndex].url}`;
        if (!src) return;
        image.src = src;
        //NOTE double image, avoid flashing by "swapping" with previous image
        imagesPerView = {
          ...imagesPerView,
          [key]: [...(imagesPerView[key] || []), { id: urls[imageIndex].id, element: image }].slice(
            -2,
          ),
        };
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
      //update
      updated_annotations = annotations.map((ann) => (ann.id === update_ann.id ? update_ann : ann));
      saveData = {
        change_type: "update",
        object: update_ann,
      };
    } else {
      //updated an interpolated annotation: create it
      //use start ann of interpolated as base for new ann
      let new_ann: Annotation;
      if (shape.type === "bbox") {
        const interpolated_box = $current_itemBBoxes.find((box) => box.id === shape.shapeId);
        if (interpolated_box && "startRef" in interpolated_box) {
          const newBBox = structuredClone(interpolated_box.startRef as BBox);
          newBBox.id = shape.shapeId;
          newBBox.data.coords = shape.coords;
          newBBox.data.view_ref = shape.viewRef;
          newBBox.ui.frame_index = currentFrame;
          newBBox.updated_at = new Date(Date.now()).toISOString();
          new_ann = newBBox;
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
            new_ann = newKpt;
          }
        }
      } else if (shape.type === "mask") {
        console.log("TODO! mask");
        //mask not implemented yet in video
      }
      //update
      //TODO note: lint warnings because KPT and mask not covered yet. (new_ann not set in these cases))
      updated_annotations = [...annotations, new_ann];
      saveData = {
        change_type: "add",
        object: new_ann,
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
