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
  import type { ImageDatasetItem, SelectionTool, Shape } from "@pixano/core";

  import {
    newShape as newShapeStore,
    itemObjects,
    canSave,
    itemBboxes,
    itemMasks,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { updateExistingObject } from "../../lib/api/objectsApi";

  export let selectedItem: ImageDatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

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

  let newShape: Shape;

  $: {
    newShapeStore.set(newShape);
    if (newShape?.status === "editing") {
      itemObjects.update((oldObjects) => updateExistingObject(oldObjects, newShape));
      canSave.update((old) => {
        if (old) return old;
        if (newShape?.status === "editing" && newShape.type !== "none") {
          return true;
        }
        return false;
      });
    }
  }

  $: newShapeStore.subscribe((value) => {
    newShape = value;
  });

  let allIds: string[] = [];

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
  });
</script>

{#key selectedItem.id}
  <Canvas2D
    {imagesPerView}
    selectedItemId={selectedItem.id}
    colorRange={allIds}
    bboxes={$itemBboxes}
    masks={$itemMasks}
    {embeddings}
    bind:selectedTool
    bind:currentAnn
    bind:newShape
  />
{/key}
