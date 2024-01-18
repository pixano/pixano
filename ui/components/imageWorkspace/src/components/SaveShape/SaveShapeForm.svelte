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

  import { Button, Input, Checkbox, Combobox } from "@pixano/core/src";
  import type { FeatureValues, ItemObject, Shape } from "@pixano/core";

  import { newShape, itemObjects, canSave, itemMetas } from "../../lib/stores/imageWorkspaceStores";
  import {
    createObjectInputsSchema,
    createSchemaFromFeatures,
  } from "../../lib/settings/objectValidationSchemas";
  import { GROUND_TRUTH } from "../../lib/constants";
  import type { CreateObjectInputs, CreateObjectSchema } from "../../lib/types/imageWorkspaceTypes";
  import { mapShapeInputsToFeatures } from "../../lib/api/featuresApi";
  import { defaultObjectFeatures } from "../../lib/settings/defaultFeatures";

  let shape: Shape;
  let isFormValid: boolean = false;

  let objectProperties: { [key: string]: FeatureValues } = {};
  let formInputs: CreateObjectInputs = [];
  let objectValidationSchema: CreateObjectSchema;

  itemMetas.subscribe((metas) => {
    const itemFeaturesArray = Object.values(metas.itemFeatures || defaultObjectFeatures).map(
      (feature) => ({
        ...feature,
        label: feature.name,
        required: true,
        type: feature.dtype,
      }),
    );
    objectValidationSchema = createSchemaFromFeatures(itemFeaturesArray);
    formInputs = createObjectInputsSchema.parse(itemFeaturesArray);
  });

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);
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
    {#each formInputs as feature, i}
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
            <Input
              on:input={(e) => handleInputChange(e.currentTarget.value, feature.name)}
              on:keyup={(e) => e.stopPropagation()}
            />
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
