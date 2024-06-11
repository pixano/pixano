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
  import { Loader2Icon } from "lucide-svelte";
  import * as ort from "onnxruntime-web";
  import { Canvas2D } from "@pixano/canvas2d";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { ImageDatasetItem, ItemView } from "@pixano/core";

  import {
    newShape,
    itemBboxes,
    itemMasks,
    selectedTool,
    itemObjects,
    preAnnotationIsActive,
    colorScale,
    filters,
    itemMetas,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import { Image as ImageJS } from "image-js";

  export let selectedItem: ImageDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  let imagesPerView: Record<string, HTMLImageElement[]> = {};
  let loaded: boolean = false;

  const normalizeRange = (image: ImageJS, min: number, max: number) => {
    image.bitDepth = 8;
    image.maxValue = 255;

    const nPixels = image.size;
    for (let i = 0; i < nPixels; ++i) {
      let pixel = image.data[i];
      if (pixel < min) {
        pixel = 0;
      } else if (pixel > max) {
        pixel = 255;
      } else {
        pixel = ((pixel - min) / (max - min)) * 255;
      }
      image.data[i] = pixel;
    }
  };

  async function loadImages(views: Record<string, ItemView>) {
    let images: Record<string, HTMLImageElement[]> = {};
    const promises = Object.entries(views).map(async ([key, value]) => {
      const img = await ImageJS.load(`/${value.uri}`);

      $itemMetas.color = img.channels == 1 ? "grayscale" : "rgba";
      $itemMetas.format = img.bitDepth == 8 ? "8bit" : "16bit";

      if ($itemMetas.format == "16bit" && $itemMetas.color == "grayscale") {
        if ($filters.u16BitRange)
          normalizeRange(img, $filters.u16BitRange[0], $filters.u16BitRange[1]);

        const image = new Image();
        image.src = await img.toDataURL();
        images[key] = [image];
      } else {
        images = Object.entries(selectedItem.views).reduce(
          (acc, [key, value]) => {
            const image = new Image();
            image.src = `/${value.uri}`;
            acc[key] = [image];
            return acc;
          },
          {} as Record<string, HTMLImageElement[]>,
        );
      }
    });

    await Promise.all(promises);
    return images;
  }

  async function updateImages() {
    if (selectedItem.views) {
      loaded = false;
      imagesPerView = await loadImages(selectedItem.views);
      loaded = true;
    }
  }

  // Reactive statement to update images when selectedItem changes
  $: if (selectedItem || $filters.u16BitRange) updateImages();

  $: {
    if ($newShape?.status === "editing" && !$preAnnotationIsActive) {
      itemObjects.update((objects) => updateExistingObject(objects, $newShape));
    }
  }

  $: selectedTool.set($selectedTool);
</script>

{#key selectedItem.id}
  {#if loaded}
    <Canvas2D
      {imagesPerView}
      {loaded}
      selectedItemId={selectedItem.id}
      colorScale={$colorScale[1]}
      bboxes={$itemBboxes}
      masks={$itemMasks}
      {embeddings}
      {filters}
      bind:selectedTool={$selectedTool}
      bind:currentAnn
      bind:newShape={$newShape}
    />
  {:else}
    <div class="w-full h-full flex items-center justify-center">
      <Loader2Icon class="h-10 w-10 animate-spin stroke-white" />
    </div>
  {/if}
{/key}
