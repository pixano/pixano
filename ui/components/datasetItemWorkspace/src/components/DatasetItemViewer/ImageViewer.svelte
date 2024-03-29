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
  import type { DatasetItem, Shape } from "@pixano/core";

  import {
    newShape as newShapeStore,
    itemObjects,
    canSave,
    itemBboxes,
    itemMasks,
    preAnnotationIsActive,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { updateExistingObject } from "../../lib/api/objectsApi";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  let newShape: Shape;
  let allIds: string[] = [];

  $: {
    newShapeStore.set(newShape);
    if (newShape?.status === "editing" && !$preAnnotationIsActive) {
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

  $: selectedTool.set($selectedTool);

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
  });
</script>

{#key selectedItem.id}
  <Canvas2D
    {selectedItem}
    colorRange={allIds}
    bboxes={$itemBboxes}
    masks={$itemMasks}
    {embeddings}
    bind:selectedTool={$selectedTool}
    bind:currentAnn
    bind:newShape
  />
{/key}
