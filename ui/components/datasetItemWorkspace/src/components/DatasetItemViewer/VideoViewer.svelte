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

  // let views = selectedItem.views;
  let isLoaded = false; // TODO : refactor when images come from the server

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

  const updateView = (imageIndex: number) => {
    const image = new Image();
    const src = imagesFilesUrl[imageIndex];
    if (!src) return;
    image.src = src;
    imagesPerView.image = [...(imagesPerView.image || []), image].slice(-2);
  };
</script>

<div class="pl-4 w-full flex flex-col h-full">
  {#if isLoaded}
    <Canvas2D
      selectedItemId={selectedItem.id}
      {imagesPerView}
      colorRange={[]}
      bboxes={$itemBboxes}
      masks={$itemMasks}
      {embeddings}
      bind:selectedTool
      bind:currentAnn
      bind:newShape={$newShape}
    />
  {/if}
  <VideoPlayer {updateView} />
</div>
