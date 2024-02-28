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
  import { newShape, itemBboxes, itemMasks } from "../../lib/stores/datasetItemWorkspaceStores";
  import VideoPlayer from "../VideoPlayer/VideoPlayer.svelte";
  import { onMount } from "svelte";

  export let selectedItem: VideoDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  const imageFiles = import.meta.glob("../../assets/videos/mock/*.png") || {};

  let imagesPerView: Record<string, HTMLImageElement[]> = {};
  let imagesFilesUrl: string[] = [];
  let isLoaded = false;
  let bboxes = $itemBboxes;

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
  });

  itemBboxes.subscribe((value) => {
    bboxes = value;
  });

  const updateView = (imageIndex: number) => {
    const image = new Image();
    const src = imagesFilesUrl[imageIndex];
    if (!src) return;
    image.src = src;
    imagesPerView.image = [...(imagesPerView.image || []), image].slice(-2);
    bboxes = bboxes.map((box) => {
      const currentCoordinates = box.coordinates?.find(
        (coord) => coord.startIndex < imageIndex && coord.endIndex > imageIndex,
      );
      if (!currentCoordinates) return box;
      const startX = currentCoordinates.start[0];
      const startY = currentCoordinates.start[1];
      const xInterpolation =
        (currentCoordinates?.end[0] - currentCoordinates?.start[0]) /
        (currentCoordinates?.endIndex - currentCoordinates?.startIndex);
      const yInterpolation =
        (currentCoordinates?.end[1] - currentCoordinates?.start[1]) /
        (currentCoordinates?.endIndex - currentCoordinates?.startIndex);
      const newX = startX + xInterpolation * (imageIndex - currentCoordinates?.startIndex);
      const newY = startY + yInterpolation * (imageIndex - currentCoordinates?.startIndex);
      return {
        ...box,
        bbox: [newX, newY, box.bbox[2], box.bbox[3]],
      };
    });
  };
</script>

<div class="pl-4 h-full w-full flex flex-col">
  {#if isLoaded}
    <div class="overflow-hidden grow bg-blue-500">
      <Canvas2D
        selectedItemId={selectedItem.id}
        {imagesPerView}
        colorRange={[]}
        {bboxes}
        masks={$itemMasks}
        {embeddings}
        bind:selectedTool
        bind:currentAnn
        bind:newShape={$newShape}
      />
    </div>
    <div class="h-full grow max-h-[25%]">
      <VideoPlayer {updateView} objects={selectedItem.objects} />
    </div>
  {/if}
</div>
