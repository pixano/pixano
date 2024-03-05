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

  import type { SelectionTool, VideoDatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import {
    itemBboxes,
    itemMasks,
    itemObjects,
    newShape,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { inflexionPointBeingEdited, lastFrameIndex } from "../../lib/stores/videoViewerStores";

  import VideoPlayer from "../VideoPlayer/VideoPlayer.svelte";
  import { onMount } from "svelte";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import { linearInterpolation } from "../../lib/api/videoApi";

  export let selectedItem: VideoDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let colorRange: string[];

  const imageFiles = import.meta.glob("../../assets/videos/mock/*.png") || {};

  let imagesPerView: Record<string, HTMLImageElement[]> = {};
  let imagesFilesUrl: string[] = [];
  let isLoaded = false;

  interface ImageModule {
    default: string;
  }

  onMount(async () => {
    const imagesFilesPromises = await Promise.all(
      Object.values(imageFiles).map((image) => image()),
    );
    imagesFilesUrl = imagesFilesPromises.map((image) => {
      const typedImage = image as ImageModule;
      return typedImage.default;
    });

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
        const box = object.bbox;
        if (!box || !box.breakPointsIntervals) return object;
        const [x, y] = linearInterpolation(box.breakPointsIntervals, imageIndex);
        const coords = [x, y, box.coords[2], box.coords[3]];
        return {
          ...object,
          bbox: {
            ...box,
            coords,
          },
        };
      }),
    );
  };

  $: {
    const shape = $newShape;
    if ($newShape?.status === "editing") {
      if ($inflexionPointBeingEdited) {
        itemObjects.update((objects) =>
          objects.map((object) => {
            if (
              shape.status === "editing" &&
              shape.type === "rectangle" &&
              shape.coords &&
              object.id === shape.shapeId &&
              object.bbox
            ) {
              object.bbox = {
                ...object.bbox,
                // coordinates: object.bbox.coordinates?.map((coordinate) => {
                //   if (coordinate.frameIndex === $inflexionPointBeingEdited?.frameIndex) {
                //     coordinate.coordinates = shape.coords;
                //     return coordinate;
                //   }
                //   return coordinate;
                // }),
              };
            }
            return object;
          }),
        );
      } else {
        itemObjects.update((oldObjects) => updateExistingObject(oldObjects, $newShape));
      }
    }
  }
</script>

<section class="pl-4 h-full w-full flex flex-col">
  {#if isLoaded}
    <div class="overflow-hidden grow bg-blue-500">
      <Canvas2D
        selectedItemId={selectedItem.id}
        {imagesPerView}
        {colorRange}
        bboxes={$itemBboxes}
        masks={$itemMasks}
        {embeddings}
        bind:selectedTool
        bind:currentAnn
        bind:newShape={$newShape}
      />
    </div>
    <div class="h-full grow max-h-[25%]">
      <VideoPlayer {updateView} />
    </div>
  {/if}
</section>
