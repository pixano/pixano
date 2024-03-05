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

  import { Button } from "@pixano/core/src";
  import { nanoid } from "nanoid";

  import type { ItemObject, Shape } from "@pixano/core";

  import {
    newShape,
    itemObjects,
    itemMetas,
    canSave,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { GROUND_TRUTH } from "../../lib/constants";
  import type {
    CreateObjectInputs,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import { mapShapeInputsToFeatures, addNewInput } from "../../lib/api/featuresApi";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import { lastFrameIndex } from "../../lib/stores/videoViewerStores";

  export let currentTab: "scene" | "objects";
  let shape: Shape;
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: ObjectProperties = {};

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);
    itemObjects.update((oldObjects) => {
      if (shape.status !== "inProgress") return oldObjects;
      let newObject: ItemObject | null = null;
      const baseObject = {
        id: nanoid(10),
        item_id: shape.itemId,
        source_id: GROUND_TRUTH,
        view_id: shape.viewId,
        features,
      };
      if (shape.type === "rectangle") {
        const { x, y, width, height } = shape.attrs;
        const coords = [
          x / shape.imageWidth,
          y / shape.imageHeight,
          width / shape.imageWidth,
          height / shape.imageHeight,
        ];
        newObject = {
          ...baseObject,
          bbox: {
            coords,
            breakPointsIntervals: [
              {
                start: 0,
                end: $lastFrameIndex,
                breakPoints: [
                  { frameIndex: 0, x: coords[0], y: coords[1] },
                  { frameIndex: $lastFrameIndex, x: coords[0], y: coords[1] },
                ],
              },
            ],
            format: "xywh",
            is_normalized: true,
            confidence: 1,
          },
        };
      }
      if (shape.type === "mask") {
        newObject = {
          ...baseObject,
          mask: {
            counts: shape.rle.counts,
            size: shape.rle.size,
          },
        };
      }

      return [...oldObjects, ...(newObject ? [newObject] : [])];
    });

    for (let feat in objectProperties) {
      if (typeof objectProperties[feat] === "string") {
        addNewInput($itemMetas.featuresList, "objects", feat, objectProperties[feat] as string);
      }
    }

    newShape.set({ status: "none", shouldReset: true });
    canSave.set(true);
    currentTab = "objects";
  };

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      newShape.set({ status: "none", shouldReset: true });
    }
  }
</script>

{#if shape.status === "inProgress"}
  <form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
    <p>Save {shape.type}</p>
    <div class="max-h-[calc(100vh-250px)] overflow-y-auto flex flex-col gap-4">
      <CreateFeatureInputs bind:isFormValid bind:formInputs bind:objectProperties />
    </div>
    <div class="flex gap-4">
      <Button
        class="text-white"
        on:click={() => newShape.set({ status: "none", shouldReset: true })}>Cancel</Button
      >
      <Button class="text-white" type="submit" disabled={!isFormValid}>Confirm</Button>
    </div>
  </form>
{/if}
<svelte:window on:keydown={handleKeyDown} />
