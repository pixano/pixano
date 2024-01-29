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

  import { Check, BoxSelectIcon, Filter } from "lucide-svelte";
  import { PrimaryButton, Slider, IconButton, Switch } from "@pixano/core";
  import type { ItemObject } from "@pixano/core";
  import FeatureFormInputs from "../Features/FeatureFormInputs.svelte";
  import { itemObjects } from "../../lib/stores/imageWorkspaceStores";
  import { GROUND_TRUTH } from "../../lib/constants";

  export let objectsToAnnotate: ItemObject[] = [];
  export let colorScale: (id: string) => string;

  let isFormValid: boolean = false;
  let preAnnotationIsActive: boolean = false;
  let confidenceFilterValue = [0];
  let objectToAnnotate: ItemObject = objectsToAnnotate[0];
  let filteredObjects: ItemObject[] = [];
  let color: string;

  $: {
    color = colorScale(objectToAnnotate?.id);
  }

  $: sortedObjects = objectsToAnnotate.sort((a, b) => {
    const confidenceA = a.bbox?.confidence || 0;
    const confidenceB = b.bbox?.confidence || 0;
    return confidenceB - confidenceA;
  });

  $: {
    filteredObjects = sortedObjects.filter((object) => {
      const confidence = object.bbox?.confidence || 0;
      return confidence >= confidenceFilterValue[0];
    });
  }

  $: {
    const noObjectToAnnotate = filteredObjects.every(
      (object) => object.id !== objectToAnnotate?.id,
    );
    if (noObjectToAnnotate) {
      objectToAnnotate = filteredObjects[0];
    }
  }

  $: currentObjectIndex = filteredObjects.findIndex((object) => object.id === objectToAnnotate.id);

  $: {
    itemObjects.update((objects) =>
      objects.map((object) => {
        object.highlighted = preAnnotationIsActive ? "none" : "all";
        if (object.id === objectToAnnotate?.id && preAnnotationIsActive) {
          object.highlighted = "self";
        }
        return object;
      }),
    );
  }

  const highlightNextItem = () => {
    const nextObject = filteredObjects[currentObjectIndex + 1];
    if (nextObject) {
      objectToAnnotate = nextObject;
    } else {
      objectToAnnotate = filteredObjects[0];
    }
  };

  const handleAcceptItem = () => {
    itemObjects.update((objects) => [
      ...objects.map((object) => {
        if (object.id === objectToAnnotate.id) {
          object.preAnnotation = "accepted";
        }
        return object;
      }),
      { ...objectToAnnotate, preAnnotation: "accepted", source_id: GROUND_TRUTH },
    ]);
    highlightNextItem();
  };

  const handleRejectItem = () => {
    itemObjects.update((objects) => objects.filter((object) => object.id !== objectToAnnotate.id));
    highlightNextItem();
  };
</script>

<div class="my-4">
  <div class="flex justify-between my-4">
    <div class="flex gap-4">
      <Switch bind:checked={preAnnotationIsActive} />
      <h3 class="uppercase font-light">PRE ANNOTATION</h3>
    </div>
    {#if preAnnotationIsActive}
      <span>{currentObjectIndex + 1} / {filteredObjects.length}</span>
    {/if}
  </div>
  {#if preAnnotationIsActive}
    <div class="my-2 flex items-center">
      <IconButton tooltipContent="confidence slider">
        <Filter />
      </IconButton>
      <div class="px-8 w-full">
        <Slider bind:value={confidenceFilterValue} max={1} step={0.01} />
      </div>
    </div>
    {#if objectToAnnotate}
      <div class="bg-white rounded-sm p-4 mt-4">
        <p class="flex gap-2">
          <BoxSelectIcon {color} />
          <span>{objectToAnnotate.id}</span>
        </p>
        <div class="flex flex-col gap-4 py-4">
          <FeatureFormInputs bind:isFormValid initialValues={objectToAnnotate.features} />
        </div>
        <div class="flex gap-4 mt-4 w-full justify-center">
          <PrimaryButton on:click={handleAcceptItem} isSelected disabled={!isFormValid}
            ><Check />Accept</PrimaryButton
          >
          <PrimaryButton on:click={handleRejectItem}>Ignore</PrimaryButton>
        </div>
      </div>
    {/if}
  {/if}
</div>
