<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { BoxSelectIcon, Check, Filter } from "lucide-svelte";

  import { Annotation, cn, IconButton, PrimaryButton, SliderWithValue, Switch } from "@pixano/core";
  import * as Tooltip from "@pixano/core/src/components/ui/tooltip";

  import {
    getObjectsToPreAnnotate,
    mapObjectWithNewStatus,
    sortAndFilterObjectsToAnnotate,
  } from "../../lib/api/objectsApi";
  import {
    annotations,
    colorScale,
    preAnnotationIsActive,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import type { ObjectProperties } from "../../lib/types/datasetItemWorkspaceTypes";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";

  let objectsToAnnotate: Annotation[] = [];
  let filteredObjectsToAnnotate: Annotation[] = [];
  let isFormValid: boolean = false;
  let confidenceFilterValue = [0];
  let color: string;
  let objectProperties: ObjectProperties = {};

  $: objectToAnnotate = filteredObjectsToAnnotate[0];
  $: color = $colorScale[1](objectToAnnotate?.id || "");

  annotations.subscribe((objects) => {
    objectsToAnnotate = getObjectsToPreAnnotate(objects);
    filteredObjectsToAnnotate = sortAndFilterObjectsToAnnotate(
      objectsToAnnotate,
      confidenceFilterValue,
      $currentFrameIndex,
    );
  });

  $: {
    if ($preAnnotationIsActive && objectsToAnnotate.length === 0) {
      preAnnotationIsActive.set(false);
      annotations.update((objects) =>
        objects.map((object) => {
          object.ui.highlighted = "all";
          return object;
        }),
      );
    }
  }

  const onAcceptItem = () => {
    objectToAnnotate.review_state = "accepted";
    objectToAnnotate.ui.highlighted = "none";

    annotations.update((objects) => [
      ...mapObjectWithNewStatus(objects, filteredObjectsToAnnotate, "accepted", objectProperties),
      objectToAnnotate,
    ]);
  };

  const onRejectItem = () => {
    annotations.update((objects) =>
      mapObjectWithNewStatus(objects, filteredObjectsToAnnotate, "rejected"),
    );
  };

  const onSwitchChange = (checked: boolean | undefined) => {
    $preAnnotationIsActive = checked || false;
    annotations.update((objects) => {
      const objectsToPreAnnotate = getObjectsToPreAnnotate(objects);
      const tempObjects = sortAndFilterObjectsToAnnotate(
        objectsToPreAnnotate,
        confidenceFilterValue,
        $currentFrameIndex,
      );
      return objects.map((object) => {
        object.ui.highlighted = $preAnnotationIsActive ? "none" : "all";
        if (object.id === tempObjects[0]?.id && $preAnnotationIsActive) {
          object.ui.highlighted = "self";
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
      $currentFrameIndex,
    );
    if (objectsToAnnotate.length === 0) {
      preAnnotationIsActive.set(false);
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
    {#if $preAnnotationIsActive}
      <span>{filteredObjectsToAnnotate.length}</span>
    {/if}
  </div>
  {#if $preAnnotationIsActive}
    <div class="my-2 flex items-center">
      <IconButton tooltipContent="confidence slider">
        <Filter />
      </IconButton>
      <div class="px-8 w-full">
        <SliderWithValue onChange={onSliderChange} max={1} step={0.01} />
      </div>
    </div>
    {#if objectToAnnotate}
      <div class="bg-white rounded-sm p-4 pb-0 mt-4 relative max-h-[60vh] overflow-y-auto">
        <p class="flex gap-2">
          <BoxSelectIcon {color} />
          <span>{objectToAnnotate.id}</span>
        </p>
        <div class="flex flex-col gap-4 py-4">
          {#key objectToAnnotate.id}
            <CreateFeatureInputs
              bind:isFormValid
              initialValues={objectToAnnotate.features}
              bind:objectProperties
              isAutofocusEnabled={false}
            />
          {/key}
        </div>
        <div class="flex gap-4 mt-4 justify-center sticky bottom-0 pb-2 left-[50%] bg-white">
          <PrimaryButton on:click={onAcceptItem} isSelected disabled={!isFormValid}>
            <Check />Accept
          </PrimaryButton>
          <PrimaryButton on:click={onRejectItem}>Reject</PrimaryButton>
        </div>
      </div>
    {/if}
  {/if}
{/if}
