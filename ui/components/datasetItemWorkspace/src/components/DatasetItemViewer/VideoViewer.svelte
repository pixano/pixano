<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  import * as ort from "onnxruntime-web";

  import { type EditShape, type VideoDatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import {
    itemBboxes,
    itemMasks,
    itemObjects,
    newShape,
    selectedTool,
    colorScale,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    lastFrameIndex,
    currentFrameIndex,
    objectIdBeingEdited,
  } from "../../lib/stores/videoViewerStores";

  import { onMount } from "svelte";
  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import { editKeyBoxInTracklet, linearInterpolation } from "../../lib/api/videoApi";

  export let selectedItem: VideoDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let brightness: number;
  export let contrast: number;

  let height = 250;
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

  const updateView = (imageIndex: number) => {
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
        const { displayedBox } = object;
        const newCoords = linearInterpolation(object.track, imageIndex);
        if (newCoords) {
          const [x, y, width, height] = newCoords;
          displayedBox.coords = [x, y, width, height];
        }
        displayedBox.displayControl = { ...displayedBox.displayControl, hidden: !newCoords };
        displayedBox.hidden = !newCoords;
        return { ...object, displayedBox };
      }),
    );

    currentFrame = imageIndex;
  };

  const updateOrCreateBox = (shape: EditShape) => {
    const currentFrame = $currentFrameIndex;
    if (shape.type === "rectangle") {
      itemObjects.update((objects) =>
        editKeyBoxInTracklet(objects, shape, currentFrame, $objectIdBeingEdited),
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
      height = document.body.scrollHeight - e.pageY;
    }
  };
</script>

<section
  class="pl-4 h-full w-full flex flex-col max-h-[calc(100vh-80px)]"
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
        {embeddings}
        {brightness}
        {contrast}
        bind:selectedTool={$selectedTool}
        bind:currentAnn
        bind:newShape={$newShape}
      />
    </div>
    <button class="h-1 bg-primary-light cursor-row-resize w-full" on:mousedown={startExpand} />
    <div class="h-full grow max-h-[25%] overflow-hidden" style={`max-height: ${height}px`}>
      <VideoInspector {updateView} />
    </div>
  {/if}
</section>
