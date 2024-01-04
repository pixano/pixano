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

  import { Button } from "@pixano/core/src/lib/components/ui/button";
  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import Combobox from "@pixano/core/src/lib/components/ui/combobox/combobox.svelte";
  import type { FeatureValues, ItemFeature, ItemObject, Shape } from "@pixano/core";

  import { newShape, itemObjects, canSave } from "../../lib/stores/imageWorkspaceStores";
  import {
    userObjectSetup as objectSetup,
    objectValidationSchema,
  } from "../../lib/settings/objectValidationSchemas";
  import { GROUND_TRUTH } from "../../lib/constants";

  let shape: Shape;
  let isFormValid: boolean = false;

  let objectProperties: { [key: string]: FeatureValues } = {};

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    const features = Object.entries(objectProperties).reduce(
      (acc, [key, value]) => {
        acc[key] = {
          name: key,
          dtype: objectSetup.find((o) => o.name === key)?.type as ItemFeature["dtype"],
          value,
        };
        return acc;
      },
      {} as Record<string, ItemFeature>,
    );
    itemObjects.update((oldObjects) => {
      if (shape.status !== "inProgress") return oldObjects;
      let newObject: ItemObject | null = null;
      const baseObject = {
        id: `object${oldObjects.length + 1}`,
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

  const handleInputChange = (value: string | number | boolean, propertyLabel: string) => {
    objectProperties[propertyLabel] = value;
  };

  $: {
    const result = objectValidationSchema.safeParse(objectProperties);
    isFormValid = result.success;
  }
</script>

{#if shape.status === "inProgress"}
  <form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
    <p>Sauvegarde {shape.type}</p>
    {#each objectSetup as feature, i}
      {#if feature.type === "boolean"}
        <div class="flex gap-4 items-center">
          <Checkbox handleClick={(checked) => handleInputChange(checked, feature.name)} />
          <span
            >{feature.label}
            {#if feature.required}
              <span>*</span>
            {/if}
          </span>
        </div>
      {/if}
      {#if feature.type === "list"}
        <Combobox
          placeholder={`Select a ${feature.label}`}
          listItems={feature.options}
          saveValue={(value) => handleInputChange(value, feature.name)}
        />
      {/if}
      {#if feature.type === "text"}
        <div>
          <span
            >{feature.label}
            {#if feature.required}
              <span>*</span>
            {/if}
          </span>
          {#if i === 0}
            <Input
              on:input={(e) => handleInputChange(e.currentTarget.value, feature.name)}
              autofocus
            />
          {:else}
            <Input on:input={(e) => handleInputChange(e.currentTarget.value, feature.name)} />
          {/if}
        </div>
      {/if}
      {#if feature.type === "number"}
        <div>
          <span
            >{feature.label}
            {#if feature.required}
              <span>*</span>
            {/if}
          </span>
          <Input
            type="number"
            on:change={(e) => handleInputChange(Number(e.currentTarget.value), feature.name)}
          />
        </div>
      {/if}
    {/each}
    <div class="flex gap-4">
      <Button
        class="text-white"
        on:click={() => newShape.update((old) => ({ ...old, status: "none" }))}>cancel</Button
      >
      <Button class="text-white" type="submit" disabled={!isFormValid}>confirm</Button>
    </div>
  </form>
{/if}
