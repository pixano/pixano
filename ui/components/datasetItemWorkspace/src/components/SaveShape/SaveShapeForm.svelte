<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Button } from "@pixano/core/src";

  import type { ItemObject, Shape } from "@pixano/core";

  import {
    newShape,
    itemObjects,
    itemMetas,
    canSave,
  } from "../../lib/stores/datasetItemWorkspaceStores";

  import type {
    CreateObjectInputs,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import { mapShapeInputsToFeatures, addNewInput } from "../../lib/api/featuresApi";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import { currentFrameIndex, objectIdBeingEdited } from "../../lib/stores/videoViewerStores";
  import { defineCreatedObject } from "../../lib/api/objectsApi";

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
    let newObject: ItemObject | null = null;
    itemObjects.update((oldObjects) => {
      if (shape.status !== "saving") return oldObjects;
      newObject = defineCreatedObject(shape, $itemMetas.type, features, $currentFrameIndex);
      objectIdBeingEdited.set(newObject?.id || null);
      const objectsWithoutHighlighted: ItemObject[] = oldObjects.map((object) => ({
        ...object,
        highlighted: "none",
        displayControl: { ...object.displayControl, editing: false },
      }));
      return [...objectsWithoutHighlighted, ...(newObject ? [newObject] : [])];
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

{#if shape.status === "saving"}
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
