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

  import { Input, Checkbox, Combobox } from "@pixano/core/src";
  import type { FeatureValues, ItemFeature } from "@pixano/core";

  import { itemMetas } from "../../lib/stores/imageWorkspaceStores";
  import { datasetsStore, currentDatasetIdStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";

  import {
    createObjectInputsSchema,
    createSchemaFromFeatures,
  } from "../../lib/settings/objectValidationSchemas";
  import type { CreateObjectInputs, CreateObjectSchema } from "../../lib/types/imageWorkspaceTypes";

  import { defaultObjectFeatures } from "../../lib/settings/defaultFeatures";

  export let isFormValid: boolean = false;
  export let formInputs: CreateObjectInputs = [];
  export let objectProperties: { [key: string]: FeatureValues } = {};
  export let initialValues: Record<string, ItemFeature> = {};

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

  $: featuresValues = $datasetsStore.find((ds)=>ds.id === $currentDatasetIdStore)?.features_values

  const handleInputChange = (value: string | number | boolean, propertyLabel: string) => {
    objectProperties[propertyLabel] = value;
  };

  $: {
    Object.values(initialValues).forEach((feature) => {
      if (typeof feature.value !== "object") {
        objectProperties[feature.name] = feature.value;
      }
    });
  }

  $: {
    const result = objectValidationSchema.safeParse(objectProperties);
    isFormValid = result.success;
  }
</script>

{#each formInputs as feature, i}
  {#if feature.type === "bool"}
    <div class="flex gap-4 items-center">
      <Checkbox
        handleClick={(checked) => handleInputChange(checked, feature.name)}
        checked={initialValues[feature.name]?.value === 1}
      />
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
  {#if ["int", "float", "str"].includes(feature.type)}
    <div>
      <span
        >{feature.label}
        {#if feature.required}
          <span>*</span>
        {/if}
      </span>
      {#if i === 0}
        <Input
          type={feature.type === "str" ? "text" : "number"}
          step={feature.type === "int" ? "1" : "any"}
          value={initialValues[feature.name]?.value || ""}
          list="objAvailableValues_{feature.name}"
          autofocus
          on:keyup={(e) => e.stopPropagation()}
          on:input={(e) =>
            handleInputChange(
              feature.type === "str" ? e.currentTarget.value : Number(e.currentTarget.value),
              feature.name,
            )}
        />
      {:else}
        <Input
          type={feature.type === "str" ? "text" : "number"}
          step={feature.type === "int" ? "1" : "any"}
          value={initialValues[feature.name]?.value || ""}
          list="objAvailableValues_{feature.name}"
          on:keyup={(e) => e.stopPropagation()}
          on:input={(e) =>
            handleInputChange(
              feature.type === "str" ? e.currentTarget.value : Number(e.currentTarget.value),
              feature.name,
            )}
        />
      {/if}
      <datalist id="objAvailableValues_{feature.name}">
        {#if featuresValues?.objects && feature.name in featuresValues.objects}
          {#each featuresValues.objects[feature.name].sort() as proposedValue}
            <option value={proposedValue} />
          {/each}
        {/if}
      </datalist>
    </div>
  {/if}
{/each}
