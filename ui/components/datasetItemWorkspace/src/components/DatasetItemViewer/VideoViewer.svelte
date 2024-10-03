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
    type VideoDatasetItem,
    type ImagesPerView,
  } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import {
    itemBboxes,
    itemMasks,
    annotations,
    newShape,
    selectedTool,
    colorScale,
    itemKeypoints,
    selectedKeypointsTemplate,
    imageSmoothing,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    objectIdBeingEdited,
  } from "../../lib/stores/videoViewerStores";

  import { onMount } from "svelte";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import { updateExistingObject, addOrUpdateSaveItem } from "../../lib/api/objectsApi";
  import {
    boxLinearInterpolation,
    editKeyItemInTracklet,
    keypointsLinearInterpolation,
  } from "../../lib/api/videoApi";
  import { templates } from "../../lib/settings/keyPointsTemplates";

  export let selectedItem: VideoDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  $: {
    if (selectedItem) {
      currentFrameIndex.set(0);
    }
  }

  let inspectorMaxHeight = 250;
  let expanding = false;
  let currentFrame: number = 0;

  let imagesPerView: ImagesPerView = {};

  let imagesFilesUrls: Record<string, Record<string, string>[]> = Object.entries(
    selectedItem.views,
  ).reduce(
    (acc, [key, value]) => {
      acc[key] = value.map((view) => {
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

    annotations.update((objects) => {
      objects = objects.map((object) => {
        if (object.datasetItemType !== "video") return object;
        let { displayedMBox, displayedMKeypoints } = object;

        if (object.boxes) {
          let new_displayedMBox = [];
          //Need to add bbox if not present beforehand
          for (const view in imagesPerView) {
            let frame_bbox = object.boxes.find(
              (bbox) => bbox.view_id == view && bbox.frame_index == imageIndex,
            );
            if (frame_bbox) {
              let dispViewBBox = displayedMBox
                ? displayedMBox.find((bbox) => bbox.view_id == view)
                : undefined;
              if (!dispViewBBox) {
                if (!displayedMBox) displayedMBox = [];
                displayedMBox.push(frame_bbox); // clone not required as bbox are shallow
              }
            }
          }
          if (displayedMBox) {
            for (let displayedBox of displayedMBox) {
              const newCoords = boxLinearInterpolation(
                newTrack || object.track,
                imageIndex,
                object.boxes,
                displayedBox.view_id!,
              );

              if (newCoords && newCoords.every((value) => value)) {
                displayedBox = { ...displayedBox, coords: newCoords, frame_index: imageIndex };
              }
              displayedBox.displayControl = { ...displayedBox.displayControl, hidden: !newCoords };
              new_displayedMBox.push(displayedBox);
            }
            object = { ...object, displayedMBox: new_displayedMBox };
          }
        }

        if (object.keypoints) {
          let new_displayedMKeypoints = [];
          //Need to add keypoint if not present beforehand
          for (const view in imagesPerView) {
            let frame_kpt = object.keypoints.find(
              (kpt) => kpt.view_id == view && kpt.frame_index == imageIndex,
            );
            if (frame_kpt) {
              let dispViewKpt = displayedMKeypoints
                ? displayedMKeypoints.find((kpt) => kpt.view_id == view)
                : undefined;
              if (!dispViewKpt) {
                if (!displayedMKeypoints) displayedMKeypoints = [];
                displayedMKeypoints.push(structuredClone(frame_kpt)); // clone required as keypoints are not shallow
              }
            }
          }
          if (displayedMKeypoints) {
            for (let displayedKeypoints of displayedMKeypoints) {
              const vertices = keypointsLinearInterpolation(
                object,
                imageIndex,
                displayedKeypoints.view_id!,
              );
              if (vertices) {
                displayedKeypoints = { ...displayedKeypoints, vertices, frame_index: imageIndex };
              }
              displayedKeypoints.displayControl = {
                ...displayedKeypoints.displayControl,
                hidden: !vertices,
              };
              new_displayedMKeypoints.push(displayedKeypoints);
            }
            object = { ...object, displayedMKeypoints: new_displayedMKeypoints };
          }
        }
        return object;
      });
      function findEarlierTracklet(item: ItemObject): number {
        if (item.datasetItemType !== "video") return 0;
        if (item.track.length === 0) return 0;
        return item.track.reduce(
          (min, obj) => (obj.start < min ? obj.start : min),
          item.track[0].start,
        );
      }
      objects.sort((a, b) => findEarlierTracklet(a) - findEarlierTracklet(b));
      return objects;
    });

    currentFrame = imageIndex;
  };

  const updateOrCreateBox = (shape: EditShape) => {
    const currentFrame = $currentFrameIndex;
    if (shape.type === "bbox" || shape.type === "keypoints") {
      let { objects, save_data } = editKeyItemInTracklet(
        $annotations,
        shape,
        currentFrame,
        $objectIdBeingEdited,
      );
      $annotations = objects;
      if (save_data) saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_data));
      newShape.set({ status: "none" });
    } else {
      annotations.update((objects) => updateExistingObject(objects, shape));
      if (shape.highlighted === "self") {
        objectIdBeingEdited.set(shape.shapeId);
      }
    }
  };

  $: {
    const shape = $newShape;
    if (shape.status === "editing") {
      updateOrCreateBox(shape);
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
  {#if isLoaded}
    <div class="overflow-hidden grow">
      <Canvas2D
        selectedItemId={selectedItem.id + currentFrame}
        {imagesPerView}
        colorScale={$colorScale[1]}
        bboxes={$itemBboxes}
        masks={$itemMasks}
        keypoints={$itemKeypoints}
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
      <VideoInspector {updateView} />
    </div>
  {/if}
</section>
