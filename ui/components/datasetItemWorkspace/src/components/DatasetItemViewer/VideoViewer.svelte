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

  // let views = selectedItem.views;
  let isLoaded = false; // TODO : refactor when images come from the server

  interface ImageModule {
    default: string;
  }

  onMount(async () => {
    const imagesFilesPromises = await Promise.all(
      Object.values(imageFiles).map((image) => image()),
    );
    const imagesFilesUrl = imagesFilesPromises.map((image) => {
      const typedImage = image as ImageModule;
      return typedImage.default;
    });
    console.log("selectedItem", {
      selectedItem,
      imageFiles,
      imagesFilesUrl,
      images: imagesPerView,
    });

    // const views: VideoDatasetItem["views"] = {
    //   ...selectedItem.views,
    //   images: imagesFilesUrl.map((image) => ({
    //     ...(selectedItem.views.image as unknown as ItemView),
    //     uri: image,
    //   })) as ItemView[],
    // };
    // selectedItem.views = views;
    const image = new Image();
    image.src = imagesFilesUrl[0];
    imagesPerView = {
      ...imagesPerView,
      image: [image],
    };
  });

  const updateImages = (imageUrl: string) => {
    const image = new Image();
    image.src = imageUrl;
    imagesPerView.image = [...(imagesPerView.image || []), image].slice(-2);
    isLoaded = true;
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
  <VideoPlayer updateViews={updateImages} />
</div>
