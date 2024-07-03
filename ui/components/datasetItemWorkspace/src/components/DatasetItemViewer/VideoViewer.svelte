<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import * as ort from "onnxruntime-web";

  import { type EditShape, type Tracklet, type VideoDatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import {
    itemBboxes,
    itemMasks,
    itemObjects,
    newShape,
    selectedTool,
    colorScale,
    itemKeypoints,
    selectedKeypointsTemplate,
    imageSmoothing,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    objectIdBeingEdited,
  } from "../../lib/stores/videoViewerStores";

  import { onMount } from "svelte";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import { updateExistingObject } from "../../lib/api/objectsApi";
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
  let currentFrame: number;

  let imagesPerView: Record<string, HTMLImageElement[]> = {};

  let imagesFilesUrls: Record<string, string[]> = Object.entries(selectedItem.views).reduce(
    (acc, [key, value]) => {
      acc[key] = value.map((view) => view.uri);
      return acc;
    },
    {} as Record<string, string[]>,
  );

  let isLoaded = false;

  onMount(() => {
    Object.entries(imagesFilesUrls).forEach(([key, urls]) => {
      const image = new Image();
      image.src = `/${urls[0]}`;
      imagesPerView = {
        ...imagesPerView,
        [key]: [image],
      };
    });

    isLoaded = true;
    const longestView = Object.values(imagesFilesUrls).reduce(
      (acc, urls) => (urls.length > acc ? urls.length : acc),
      0,
    );
    lastFrameIndex.set(longestView - 1);
  });

  const updateView = (imageIndex: number, newTrack: Tracklet[] | undefined = undefined) => {
    Object.entries(imagesFilesUrls).forEach(([key, urls]) => {
      const image = new Image();
      const src = `/${urls[imageIndex]}`;
      if (!src) return;
      image.src = src;
      imagesPerView = {
        ...imagesPerView,
        [key]: [...(imagesPerView[key] || []), image].slice(-2),
      };
    });

    itemObjects.update((objects) =>
      objects.map((object) => {
        if (object.datasetItemType !== "video") return object;
        let { displayedMBox, displayedMKeypoints } = object;

        if (displayedMBox && object.boxes) {
          let new_displayedMBox = [];
          for (let displayedBox of displayedMBox) {
            const newCoords = boxLinearInterpolation(
              newTrack || object.track,
              imageIndex,
              object.boxes,
              displayedBox.view_id,
            );

            if (newCoords && newCoords.every((value) => value)) {
              displayedBox = { ...displayedBox, coords: newCoords };
            }
            displayedBox.displayControl = { ...displayedBox.displayControl, hidden: !newCoords };
            new_displayedMBox.push(displayedBox);
          }
          object = { ...object, displayedMBox: new_displayedMBox };
        }
        if (displayedMKeypoints && object.keypoints) {
          let new_displayedMKeypoints = [];
          for (let displayedKeypoints of displayedMKeypoints) {
            const vertices = keypointsLinearInterpolation(object, imageIndex, displayedKeypoints.view_id);
            if (vertices) {
              displayedKeypoints = { ...displayedKeypoints, vertices };
            }
            displayedKeypoints.displayControl = { ...displayedKeypoints.displayControl, hidden: !vertices };
            new_displayedMKeypoints.push(displayedKeypoints);
          }
          object = { ...object, displayedMKeypoints: new_displayedMKeypoints };
        }
        return object;
      }),
    );

    currentFrame = imageIndex;
  };

  const updateOrCreateBox = (shape: EditShape) => {
    const currentFrame = $currentFrameIndex;
    if (shape.type === "rectangle" || shape.type === "keypoint") {
      itemObjects.update((objects) =>
        editKeyItemInTracklet(objects, shape, currentFrame, $objectIdBeingEdited),
      );
      newShape.set({ status: "none" });
    } else {
      itemObjects.update((objects) => updateExistingObject(objects, shape));
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
