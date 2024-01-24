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

  import type { FeatureValues, ItemObject, Shape } from "@pixano/core";

  import { newShape, itemObjects, canSave } from "../../lib/stores/imageWorkspaceStores";
  import { GROUND_TRUTH } from "../../lib/constants";
  import type { CreateObjectInputs } from "../../lib/types/imageWorkspaceTypes";
  import { mapShapeInputsToFeatures } from "../../lib/api/featuresApi";
  import FeatureFormInputs from "../Features/FeatureFormInputs.svelte";

  let shape: Shape;
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: { [key: string]: FeatureValues } = {};

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);
    itemObjects.update((oldObjects) => {
      if (shape.status !== "inProgress") return oldObjects;
      let newObject: ItemObject | null = null;
      const id = nanoid(10);
      const id2 = nanoid(10);
      console.log({ id, id2 });
      const baseObject = {
        id: nanoid(10),
        item_id: shape.itemId,
        source_id: GROUND_TRUTH,
        view_id: shape.viewId,
        features,
      };
      if (shape.type === "rectangle") {
        newObject = {
          ...baseObject,
          bbox: {
            coords: [
              shape.attrs.x / shape.imageWidth,
              shape.attrs.y / shape.imageHeight,
              shape.attrs.width / shape.imageWidth,
              shape.attrs.height / shape.imageHeight,
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
          isManual: !!shape.isManual,
          mask: {
            counts: shape.rle.counts,
            size: shape.rle.size,
          },
        };
      }

      return [...oldObjects, ...(newObject ? [newObject] : [])];
    });
    newShape.set({ status: "none" });
    canSave.set(true);
  };
</script>

{#if shape.status === "inProgress"}
  <form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
    <p>Sauvegarde {shape.type}</p>
    <FeatureFormInputs bind:isFormValid bind:formInputs bind:objectProperties />
    <div class="flex gap-4">
      <Button
        class="text-white"
        on:click={() => newShape.update((old) => ({ ...old, status: "none" }))}>cancel</Button
      >
      <Button class="text-white" type="submit" disabled={!isFormValid}>confirm</Button>
    </div>
  </form>
{/if}
