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
  import { nanoid } from "nanoid";

  import { PrimaryButton, Slider, IconButton, Switch, cn } from "@pixano/core";
  import type { ItemObject } from "@pixano/core";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import { canSave, itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { GROUND_TRUTH } from "../../lib/constants";
  import {
    getObjectsToPreAnnotate,
    mapObjectWithNewStatus,
    sortAndFilterObjectsToAnnotate,
  } from "../../lib/api/objectsApi";
  import * as Tooltip from "@pixano/core/src/components/ui/tooltip";
  import type { ObjectProperties } from "../../lib/types/datasetItemWorkspaceTypes";

  export let colorScale: (id: string) => string;
  export let preAnnotationIsActive: boolean = false;

  let objectsToAnnotate: ItemObject[] = [];
  let filteredObjectsToAnnotate: ItemObject[] = [];
  let isFormValid: boolean = false;
  let confidenceFilterValue = [0];
  let color: string;
  let objectProperties: ObjectProperties = {};

  $: objectToAnnotate = filteredObjectsToAnnotate[0];
  $: color = colorScale(objectToAnnotate?.id || "");

  itemObjects.subscribe((objects) => {
    objectsToAnnotate = getObjectsToPreAnnotate(objects);
    filteredObjectsToAnnotate = sortAndFilterObjectsToAnnotate(
      objectsToAnnotate,
      confidenceFilterValue,
    );
    if (objectsToAnnotate.length === 0) {
      preAnnotationIsActive = false;
    }
  });

  const onAcceptItem = () => {
    itemObjects.update((objects) => [
      ...mapObjectWithNewStatus(objects, filteredObjectsToAnnotate, "accepted", objectProperties),
      {
        ...objectToAnnotate,
        review_state: "accepted",
        source_id: GROUND_TRUTH,
        id: nanoid(10),
        highlighted: "none",
      },
    ]);
    canSave.set(true);
  };

  const onRejectItem = () => {
    itemObjects.update((objects) =>
      mapObjectWithNewStatus(objects, filteredObjectsToAnnotate, "rejected"),
    );
    canSave.set(true);
  };

  const onSwitchChange = (checked: boolean | undefined) => {
    preAnnotationIsActive = checked || false;
    itemObjects.update((objects) => {
      const objectsToPreAnnotate = getObjectsToPreAnnotate(objects);
      const tempObjects = sortAndFilterObjectsToAnnotate(
        objectsToPreAnnotate,
        confidenceFilterValue,
      );
      return objects.map((object) => {
        object.highlighted = preAnnotationIsActive ? "none" : "all";
        if (object.id === tempObjects[0]?.id && preAnnotationIsActive) {
          object.highlighted = "self";
        }
        return object;
      });
    });
  };

  const onSliderChange = (value: number[] | undefined) => {
    confidenceFilterValue = value || [0];
    filteredObjectsToAnnotate = sortAndFilterObjectsToAnnotate(
      objectsToAnnotate,
      confidenceFilterValue,
    );
    if (objectsToAnnotate.length === 0) {
      preAnnotationIsActive = false;
    }
  };
</script>

{#if objectsToAnnotate.length > 0}
  <div class="flex justify-between my-4">
    <div class="flex gap-4">
      <Tooltip.Root>
        <Tooltip.Trigger>
          <Switch
            class={cn({ "pointer-events-none": !objectsToAnnotate.length })}
            onChange={onSwitchChange}
          />
        </Tooltip.Trigger>
        {#if objectsToAnnotate.length === 0}
          <Tooltip.Content>
            <p>No objects to annotate</p>
          </Tooltip.Content>
        {/if}
      </Tooltip.Root>
      <h3 class="uppercase font-medium">PRE ANNOTATION</h3>
    </div>
    {#if preAnnotationIsActive}
      <span>{filteredObjectsToAnnotate.length}</span>
    {/if}
  </div>
  {#if preAnnotationIsActive}
    <div class="my-2 flex items-center">
      <IconButton tooltipContent="confidence slider">
        <Filter />
      </IconButton>
      <div class="px-8 w-full">
        <Slider onChange={onSliderChange} max={1} step={0.01} />
      </div>
    </div>
    {#if objectToAnnotate}
      <div class="bg-white rounded-sm p-4 pb-0 mt-4 relative max-h-[60vh] overflow-y-auto">
        <p class="flex gap-2">
          <BoxSelectIcon {color} />
          <span>{objectToAnnotate.id}</span>
        </p>
        <div class="flex flex-col gap-4 py-4">
          <CreateFeatureInputs
            bind:isFormValid
            initialValues={objectToAnnotate.features}
            bind:objectProperties
          />
        </div>
        <div class="flex gap-4 mt-4 justify-center sticky bottom-0 pb-2 left-[50%] bg-white">
          <PrimaryButton on:click={onAcceptItem} isSelected disabled={!isFormValid}
            ><Check />Accept</PrimaryButton
          >
          <PrimaryButton on:click={onRejectItem}>Reject</PrimaryButton>
        </div>
      </div>
    {/if}
  {/if}
{/if}
