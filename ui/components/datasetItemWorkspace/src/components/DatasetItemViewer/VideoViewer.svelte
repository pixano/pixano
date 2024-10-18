<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import * as ort from "onnxruntime-web";

  import {
    type EditShape,
    type Tracklet,
    DatasetItem,
    type ImagesPerView,
    Annotation,
    BBox,
    Track,
    type KeypointsTemplate,
    type SaveItem,
    SequenceFrame,
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
  entities.subscribe((entities)=>{
    tracks = entities.filter((entity)=>entity.is_track);
    console.log("changed Tracks!", tracks);
  })

  const current_itemBBoxes = derived(
    [itemBboxes, currentFrameIndex, tracklets],
    ([$itemBboxes, $currentFrameIndex, $tracklets]) => {
      //TODO now tracklets have childs, we could take advantage of it here
      const current_bboxes_and_interpolated: BBox[] = [];
      const current_tracklets = $tracklets.filter(
        (tracklet) =>
          tracklet.data.start_timestep <= $currentFrameIndex &&
          tracklet.data.end_timestep >= $currentFrameIndex,
      );
      const tracklets_bboxes: Record<string, BBox[]> = {};
      $itemBboxes.forEach((bbox) => {
        const tracklet_of_bbox = current_tracklets.find(
          (tracklet) =>
            tracklet.data.entity_ref.id === bbox.data.entity_ref.id &&
            tracklet.data.view_ref.name &&
            bbox.data.view_ref.name,
        );
        if (tracklet_of_bbox) {
          if (!tracklets_bboxes[tracklet_of_bbox.id]) tracklets_bboxes[tracklet_of_bbox.id] = [];
          tracklets_bboxes[tracklet_of_bbox.id].push(bbox);
        }
      });
      for (const tracklet_id in tracklets_bboxes) {
        const box = tracklets_bboxes[tracklet_id].find(
          (bbox) => bbox.frame_index === $currentFrameIndex,
        );
        if (box) current_bboxes_and_interpolated.push(box);
        else {
          const interpolated_box = boxLinearInterpolation(
            tracklets_bboxes[tracklet_id],
            $currentFrameIndex,
          );
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
      const tracklets_kpts: Record<string, KeypointsTemplate[]> = {};
      $itemKeypoints.forEach((kpt) => {
        const tracklet_of_kpt = current_tracklets.find(
          (tracklet) =>
            tracklet.data.entity_ref.id === kpt.entityRef?.id &&
            tracklet.data.view_ref.name &&
            kpt.viewRef?.name,
        );
        if (tracklet_of_kpt) {
          if (!tracklets_kpts[tracklet_of_kpt.id]) tracklets_kpts[tracklet_of_kpt.id] = [];
          tracklets_kpts[tracklet_of_kpt.id].push(kpt);
        }
      });
      for (const tracklet_id in tracklets_kpts) {
        const kpt = tracklets_kpts[tracklet_id].find(
          (kpt) => kpt.frame_index === $currentFrameIndex,
        );
        if (kpt) current_kpts_and_interpolated.push(kpt);
        else {
          const interpolated_kpt = keypointsLinearInterpolation(
            tracklets_kpts[tracklet_id],
            $currentFrameIndex,
          );
          if (interpolated_kpt) current_kpts_and_interpolated.push(interpolated_kpt);
        }
      }
      return current_kpts_and_interpolated;
    },
  );

  let inspectorMaxHeight = 250;
  let expanding = false;
  let currentFrame: number = 0;

  let imagesPerView: ImagesPerView = {};

  let imagesFilesUrls: Record<string, Record<string, string>[]> = Object.entries(
    selectedItem.views,
  ).reduce(
    (acc, [key, value]) => {
      acc[key] = (value as SequenceFrame[]).map((view) => {
        return { id: view.id, url: view.data.url as string };
      });
      return acc;
    },
    {} as Record<string, Record<string, string>[]>,
  );

  let isLoaded = false;

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

    updateView(0);
  });

  const updateView = (imageIndex: number, newTrack: Tracklet[] | undefined = undefined) => {
    Object.entries(imagesFilesUrls).forEach(([key, urls]) => {
      const image = new Image();
      const src = `/${urls[imageIndex].url}`;
      if (!src) return;
      image.src = src;
      imagesPerView = {
        ...imagesPerView,
        [key]: [...(imagesPerView[key] || []), { id: urls[imageIndex].id, element: image }].slice(
          -2,
        ),
      };
    });
    currentFrame = imageIndex;
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
        console.log("TODO! kpt");
        //TODO need to convert from KeypointTemplate to Keypoint
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
          newBBox.frame_index = currentFrame;
          newBBox.updated_at = new Date(Date.now()).toISOString();
          new_ann = newBBox;
        }
      } else if (shape.type === "keypoints") {
        const interpolated_kpt = $current_itemKeypoints.find((kpt) => kpt.id === shape.shapeId);
        if (interpolated_kpt && "startRef" in interpolated_kpt) {
          const newKptT = structuredClone(interpolated_kpt.startRef as KeypointsTemplate);
          newKptT.id = shape.shapeId;
          newKptT.vertices = shape.vertices;
          newKptT.viewRef = shape.viewRef;
          newKptT.frame_index = currentFrame;
          //TODO need to convert from KeypointTemplate to Keypoints
          //const newKpt = kptTemplate2Kpt(newKptT);
          //newKpt.updated_at = new Date(Date.now()).toISOString();
          //new_ann = newKpt;
        }
      } else if (shape.type === "mask") {
        console.log("TODO! mask");
        //mask not implemented yet in video
      }
      //update
      //TODO note: lint warnings because KPT and mask not covered yet. (new_ann not set in these cases))
      updated_annotations = [...$annotations, new_ann];
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
      let { objects, save_data } = editKeyItemInTracklet(
        $annotations,
        shape,
        $currentFrameIndex,
      );
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

  $: selectedTool.set($selectedTool);

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
  {#if isLoaded && $current_itemBBoxes}
    <div class="overflow-hidden grow">
      <Canvas2D
        selectedItemId={selectedItem.item.id}
        {imagesPerView}
        colorScale={$colorScale[1]}
        bboxes={$current_itemBBoxes}
        masks={$itemMasks}
        keypoints={$current_itemKeypoints}
        selectedKeypointTemplate={templates.find((t) => t.id === $selectedKeypointsTemplate)}
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
      <VideoInspector bind:tracks {updateView} />
    </div>
  {/if}
</section>
