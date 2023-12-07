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

  // import { PlusCircle } from "lucide-svelte";
  // import { z } from "zod";

  import { Button } from "@pixano/core/src/lib/components/ui/button";
  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import Combobox from "@pixano/core/src/lib/components/ui/combobox/combobox.svelte";
  import type { PropertiesValues, Shape } from "@pixano/core";

  import { newShape, itemObjects } from "../../lib/stores/stores";
  import {
    userObjectSetup as objectSetup,
    objectValidationSchema,
  } from "../../lib/settings/objectSetting";
  import SaveShapeTextInput from "./SaveShapeTextInput.svelte";

  let shape: Shape;
  let isFormValid: boolean = false;

  let objectProperties: { [key: string]: PropertiesValues } = {};

  let objectCategory: string;

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    const imageHeight = 426; // TODO100 imageHeight
    const imageWidth = 640; // TODO100

    itemObjects.update((oldObjects) => [
      {
        id: `object${oldObjects.length + 1}`,
        item_id: shape.viewId, // TODO100
        source_id: shape.viewId, // TODO100
        view_id: shape.viewId,
        bbox: {
          coords: [
            shape.attrs.x / imageWidth,
            shape.attrs.y / imageHeight,
            shape.attrs.width / imageWidth,
            shape.attrs.height / imageHeight,
          ],
          format: `bbox${oldObjects.length + 1}`,
          is_normalized: true,
          confidence: 1,
        },
        features: {
          category_id: {
            name: "category_id",
            dtype: "number",
            value: 64,
          },
          category_name: {
            name: "category_name",
            dtype: "text",
            value: (objectProperties.Label as string[])?.[0], // TODO100
          },
        },
      },
      ...oldObjects,
    ]);
    newShape.set(null);
  };

  const handleCheckboxClick = (checked: boolean, propertyLabel: string) => {
    objectProperties[propertyLabel] = checked;
  };

  const handleNumberInputChange = (value: string, propertyLabel: string) => {
    objectProperties[propertyLabel] = Number(value);
  };

  const handleTextInputChange = (value: string[], propertyLabel: string) => {
    objectProperties[propertyLabel] = value;
  };

  $: {
    const result = objectValidationSchema.safeParse(objectProperties);
    isFormValid = result.success;
  }
</script>

<form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
  <p>Sauvegarde {shape.type}</p>
  <Combobox
    placeholder="Select a category"
    bind:value={objectCategory}
    listItems={[
      { value: "category_1", label: "category 1" },
      { value: "category_2", label: "category 2" },
    ]}
  />
  {#each objectSetup as property}
    {#if property.type === "checkbox"}
      <div class="flex gap-4">
        <Checkbox handleClick={(checked) => handleCheckboxClick(checked, property.label)} />
        <span>{property.label}</span>
      </div>
    {/if}
    {#if property.type === "text"}
      <SaveShapeTextInput textProperty={property} {handleTextInputChange} />
    {/if}
    {#if property.type === "number"}
      <div>
        <span>{property.label}</span>
        <Input
          type="number"
          on:change={(e) => handleNumberInputChange(e.currentTarget.value, property.label)}
        />
      </div>
    {/if}
  {/each}
  <div class="flex gap-4">
    <Button class="text-white" on:click={() => newShape.set(null)}>cancel</Button>
    <Button class="text-white" type="submit" disabled={!isFormValid}>confirm</Button>
  </div>
</form>
