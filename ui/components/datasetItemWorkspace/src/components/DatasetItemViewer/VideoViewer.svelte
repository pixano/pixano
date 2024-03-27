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

  import { utils, type VideoDatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import {
    itemBboxes,
    itemMasks,
    itemObjects,
    newShape,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { keyFrameBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";

  import VideoPlayer from "../VideoPlayer/VideoPlayer.svelte";
  import { onMount } from "svelte";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import {
    editKeyFrameInTracklet,
    updateFrameWithInterpolatedBox,
    updateFrameWithInterpolatedMask,
  } from "../../lib/api/videoApi";

  export let selectedItem: VideoDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let colorRange: string[];

  let imagesPerView: Record<string, HTMLImageElement[]> = {};
  let imagesFilesUrl: string[] = selectedItem.views.image?.map((view) => view.uri) || [];

  let isLoaded = false;
  let colorScale = utils.ordinalColorScale(colorRange);

  onMount(() => {
    const image = new Image();
    image.src = imagesFilesUrl[0];

    imagesPerView = {
      ...imagesPerView,
      image: [image],
    };
    isLoaded = true;
    lastFrameIndex.set(imagesFilesUrl.length - 1);
  });

  const updateView = (imageIndex: number) => {
    const image = new Image();
    const src = imagesFilesUrl[imageIndex];
    if (!src) return;
    image.src = src;
    imagesPerView.image = [...(imagesPerView.image || []), image].slice(-2);
    itemObjects.update((objects) =>
      objects.map((object) => {
        if (object.datasetItemType !== "video") return object;
        const bbox = updateFrameWithInterpolatedBox(object, imageIndex);
        const mask = updateFrameWithInterpolatedMask(object, imageIndex);
        let displayedFrame = object.displayedFrame || object.track[0].keyFrames[0] || {};
        displayedFrame = {
          ...displayedFrame,
          bbox,
          mask,
          frameIndex: imageIndex,
          hidden: !bbox && !mask,
        };
        return { ...object, displayedFrame };
      }),
    );
  };

  $: {
    const shape = $newShape;
    const keyFrame = $keyFrameBeingEdited;
    if (shape.status === "editing") {
      if (keyFrame) {
        itemObjects.update((objects) => editKeyFrameInTracklet(objects, keyFrame, shape));
      } else {
        itemObjects.update((objects) => updateExistingObject(objects, $newShape));
      }
    }
  }

  $: selectedTool.set($selectedTool);
</script>

<section class="pl-4 h-full w-full flex flex-col">
  {#if isLoaded}
    <div class="overflow-hidden grow">
      <Canvas2D
        selectedItemId={selectedItem.id}
        {imagesPerView}
        {colorRange}
        bboxes={$itemBboxes}
        masks={$itemMasks}
        {embeddings}
        bind:selectedTool={$selectedTool}
        bind:currentAnn
        bind:newShape={$newShape}
      />
    </div>
    <div class="h-full grow max-h-[25%]">
      <VideoPlayer {updateView} {colorScale} />
    </div>
  {/if}
</section>
