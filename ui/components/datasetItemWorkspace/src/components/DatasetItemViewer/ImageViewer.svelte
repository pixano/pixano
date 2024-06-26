<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import * as ort from "onnxruntime-web";
  import { Canvas2D } from "@pixano/canvas2d";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { ImageDatasetItem, ItemView } from "@pixano/core";
  import { Image as ImageJS } from "image-js";

  // Import stores and API functions
  import {
    newShape,
    itemBboxes,
    itemKeypoints,
    itemMasks,
    selectedTool,
    itemObjects,
    preAnnotationIsActive,
    colorScale,
    filters,
    itemMetas,
    selectedKeypointsTemplate,
    imageSmoothing,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import { templates } from "../../lib/settings/keyPointsTemplates";

  // Attributes
  export let selectedItem: ImageDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  // Images per view type
  type ImagesPerView = Record<string, HTMLImageElement[]>;
  let imagesPerView: ImagesPerView = {};
  let loaded: boolean = false; // Loading status of images per view

  /**
   * Normalize the pixel values of an image to a specified range.
   * @param image The image to normalize.
   * @param min The minimum pixel value.
   * @param max The maximum pixel value.
   */
  const normalize16BitImage = (image: ImageJS, min: number, max: number): void => {
    image.bitDepth = 8;
    image.maxValue = 255;

    const nPixels: number = image.size;
    if (image.channels === 4) {
      for (let i = 0; i < nPixels; i += 4) {
        let rPixel: number = image.data[i];
        let gPixel: number = image.data[i + 1];
        let bPixel: number = image.data[i + 2];

        rPixel = rPixel < min ? 0 : rPixel > max ? 255 : ((rPixel - min) / (max - min)) * 255;
        gPixel = gPixel < min ? 0 : gPixel > max ? 255 : ((gPixel - min) / (max - min)) * 255;
        bPixel = bPixel < min ? 0 : bPixel > max ? 255 : ((bPixel - min) / (max - min)) * 255;

        image.data[i] = rPixel;
        image.data[i + 1] = gPixel;
        image.data[i + 2] = bPixel;
      }
    } else {
      for (let i = 0; i < nPixels; ++i) {
        let pixel: number = image.data[i];
        pixel = pixel < min ? 0 : pixel > max ? 255 : ((pixel - min) / (max - min)) * 255;
        image.data[i] = pixel;
      }
    }
  };

  /**
   * Load images from the given views.
   * @param views The views to load images from.
   * @returns A promise that resolves to the loaded images per view.
   */
  const loadImages = async (views: Record<string, ItemView>): Promise<ImagesPerView> => {
    const images: ImagesPerView = {};
    const promises: Promise<void>[] = Object.entries(views).map(async ([key, value]) => {
      const img: ImageJS = await ImageJS.load(`/${value.uri}`);

      const bitDepth = img.bitDepth as number;
      $itemMetas.format = bitDepth === 1 ? "1bit" : bitDepth === 8 ? "8bit" : "16bit";
      $itemMetas.color = img.channels === 4 ? "rgba" : img.channels === 3 ? "rgb" : "grayscale";

      if ($itemMetas.format === "16bit") {
        normalize16BitImage(img, $filters.u16BitRange[0], $filters.u16BitRange[1]);
      }

      const image: HTMLImageElement = new Image();
      image.src = img.toDataURL();
      images[key] = [image];
    });

    await Promise.all(promises);
    return images;
  };

  /**
   * Update the images based on the selected item views.
   */
  const updateImages = async (): Promise<void> => {
    if (selectedItem.views) {
      loaded = false;
      imagesPerView = await loadImages(selectedItem.views);
      loaded = true;
    }
  };

  // Reactive statement to update images when selectedItem changes or the 16 bit filters change
  let prev16BitRange: number[] = [];
  $: if (selectedItem || $filters.u16BitRange) {
    if (
      prev16BitRange[0] !== $filters.u16BitRange[0] ||
      prev16BitRange[1] !== $filters.u16BitRange[1]
    ) {
      updateImages().catch(() => {
        console.error("Error loading the images.");
      });
      prev16BitRange = [...$filters.u16BitRange];
    }
  }

  // Reactive statement to update item objects when new shape is being edited and pre-annotation is not active
  $: if ($newShape?.status === "editing" && !$preAnnotationIsActive) {
    itemObjects.update((objects) => updateExistingObject(objects, $newShape));
  }

  // Reactive statement to set the selected tool
  $: selectedTool.set($selectedTool);
</script>

<!-- Render the Canvas2D component with the loaded images or show a loading spinner -->
{#key selectedItem.id}
  {#if loaded}
    <Canvas2D
      {imagesPerView}
      {loaded}
      selectedItemId={selectedItem.id}
      colorScale={$colorScale[1]}
      bboxes={$itemBboxes}
      masks={$itemMasks}
      keypoints={$itemKeypoints}
      selectedKeypointTemplate={templates.find((t) => t.id === $selectedKeypointsTemplate)}
      {embeddings}
      {filters}
      imageSmoothing={$imageSmoothing}
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
