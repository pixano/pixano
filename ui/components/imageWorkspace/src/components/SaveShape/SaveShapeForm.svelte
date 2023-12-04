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

  import type { tools } from "@pixano/canvas2d";
  import { Button } from "@pixano/core/src/lib/components/ui/button";
  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import type { PropertiesValues } from "@pixano/core";

  import { newShape, objects } from "../../lib/stores/stores";
  import {
    userObjectSetup as objectSetup,
    objectValidationSchema,
  } from "../../lib/settings/objectSetting";
  import SaveShapeTextInput from "./SaveShapeTextInput.svelte";

  let shape: tools.Shape;
  let isFormValid: boolean = false;

  let objectProperties: { [key: string]: PropertiesValues } = {};

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    objects.update((oldObjects) => [
      ...oldObjects,
      {
        type: "box",
        name: `id ${oldObjects.length + 1}`,
        id: `${oldObjects.length + 1}`,
        boundingBox: {
          id: "23",
          viewId: "view",
          bbox: [shape.attrs.x, shape.attrs.y, shape.attrs.width, shape.attrs.height],
          tooltip: "foo",
          catId: 1,
          visible: true,
          opacity: 1,
        },
        properties: objectProperties,
      },
    ]);
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

  $: console.log({ objectProperties });
</script>

<form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
  <p>Sauvegarde{shape.type}</p>
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
