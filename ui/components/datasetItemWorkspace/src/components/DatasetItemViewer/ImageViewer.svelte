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
  import { Canvas2D } from "@pixano/canvas2d";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { ImageDatasetItem } from "@pixano/core";

  import {
    newShape,
    itemBboxes,
    itemKeyPoints,
    itemMasks,
    selectedTool,
    itemObjects,
    preAnnotationIsActive,
    colorScale,
    selectedKeyPointsTemplate,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import { templates } from "../../lib/settings/keyPointsTemplates";

  export let selectedItem: ImageDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let brightness: number;
  export let contrast: number;

  let imagesPerView: Record<string, HTMLImageElement[]> = {};

  $: {
    if (selectedItem.views) {
      imagesPerView = Object.entries(selectedItem.views).reduce(
        (acc, [key, value]) => {
          const image = new Image();
          image.src = `/${value.uri}`;
          acc[key] = [image];
          return acc;
        },
        {} as Record<string, HTMLImageElement[]>,
      );
    }
  }

  $: {
    if ($newShape?.status === "editing" && !$preAnnotationIsActive) {
      itemObjects.update((objects) => updateExistingObject(objects, $newShape));
    }
  }

  $: selectedTool.set($selectedTool);
</script>

{#key selectedItem.id}
  <Canvas2D
    {imagesPerView}
    selectedItemId={selectedItem.id}
    colorScale={$colorScale[1]}
    bboxes={$itemBboxes}
    masks={$itemMasks}
    keyPoints={$itemKeyPoints}
    selectedKeyPointTemplate={templates.find((t) => t.id === $selectedKeyPointsTemplate)}
    {embeddings}
    {brightness}
    {contrast}
    bind:selectedTool={$selectedTool}
    bind:currentAnn
    bind:newShape={$newShape}
  />
{/key}
