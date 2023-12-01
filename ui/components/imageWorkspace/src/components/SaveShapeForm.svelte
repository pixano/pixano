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

  import { PlusCircle } from "lucide-svelte";
  // import { z } from "zod";

  import type { tools } from "@pixano/canvas2d";
  import { Button } from "@pixano/core/src/lib/components/ui/button";
  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";

  import { newShape, objects } from "../lib/stores/stores";
  import { objectSetup, objectCreationFormSchema } from "../lib/settings/objectSetting";

  let shape: tools.Shape;
  let isFormValid: boolean = false;

  let objectProperties = [...objectSetup];

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const addTextInput = (propertyLabel: string) => {
    objectProperties = objectProperties.map((property) => {
      if (property.label === propertyLabel && property.type === "text" && property.multiple) {
        return {
          ...property,
          value: [...(property.value || [""]), ""],
        };
      }
      return property;
    });
  };

  const handleFormSubmit = () => {
    objects.update((value) => [
      ...value,
      {
        type: "box",
        name: `id ${value.length + 1}}`,
        id: `${value.length + 1}`,
        color: "green",
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
    console.log("checkbox clicked", checked);
    objectProperties = objectProperties.map((property) => {
      if (property.label === propertyLabel && property.type === "checkbox") {
        return {
          ...property,
          value: checked,
        };
      }
      return property;
    });
  };

  const handleNumberInputChange = (value: string, propertyLabel: string) => {
    console.log("text input changed", value);
    objectProperties = objectProperties.map((property) => {
      if (property.label === propertyLabel && property.type === "number") {
        return { ...property, value: Number(value) };
      }
      return property;
    });
  };

  const handleTextInputChange = (value: string, propertyLabel: string, index: number) => {
    objectProperties = objectProperties.map((property) => {
      if (property.label === propertyLabel && property.type === "text") {
        return {
          ...property,
          value: property.value?.map((text, i) => (i === index ? value : text)) || [value],
        };
      }
      return property;
    });
  };

  $: {
    const values = objectProperties.map((property) => property.value);
    const result = objectCreationFormSchema.safeParse(values);
    isFormValid = result.success;
  }
</script>

<p>{shape.status}</p>

<form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
  {#each objectProperties as property}
    {#if property.type === "checkbox"}
      <div class="flex gap-4">
        <Checkbox handleClick={(checked) => handleCheckboxClick(checked, property.label)} />
        <span>{property.label}</span>
      </div>
    {/if}
    {#if property.type === "text"}
      <div>
        <span>{property.label}</span>
        <div class="flex flex-col gap-2">
          {#each property.value || [""] as value, i}
            <div class="flex">
              <Input
                {value}
                on:change={(e) => handleTextInputChange(e.currentTarget.value, property.label, i)}
              />
              {#if property.multiple}
                <span
                  ><IconButton on:click={() => addTextInput(property.label)}
                    ><PlusCircle class="w-8 h-8" strokeWidth={1} /></IconButton
                  ></span
                >
              {/if}
            </div>
          {/each}
        </div>
      </div>
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
    <Button on:click={() => newShape.set(null)}>cancel</Button>
    <Button type="submit" disabled={!isFormValid}>confirm</Button>
  </div>
</form>
