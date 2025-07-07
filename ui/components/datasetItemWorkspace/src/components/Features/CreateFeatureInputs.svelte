<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { BaseSchema, type ItemFeature } from "@pixano/core";
  import { Checkbox, Combobox, Input } from "@pixano/core/src";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  //import { defaultObjectFeatures } from "../../lib/settings/defaultFeatures";
  import {
    getObjectProperties,
    getValidationSchemaAndFormInputs,
    mapFeatureList,
  } from "../../lib/api/featuresApi";
  import { itemMetas } from "../../lib/stores/datasetItemWorkspaceStores";
  import type {
    CreateObjectInputs,
    CreateObjectSchema,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";

  export let isFormValid: boolean = false;
  export let formInputs: CreateObjectInputs = [];
  export let objectProperties: ObjectProperties = {};
  export let initialValues: Record<string, Record<string, ItemFeature>> = {};
  export let isAutofocusEnabled: boolean = true;
  export let selectedEntityId: string = "new";
  export let baseSchema: BaseSchema;
  let objectValidationSchema: CreateObjectSchema;

  datasetSchema.subscribe((schema) => {
    ({ schema: objectValidationSchema, inputs: formInputs } = getValidationSchemaAndFormInputs(
      schema,
      baseSchema,
    ));
  });

  const handleInputChange = (
    value: string | number | boolean,
    propertyLabel: string,
    tname: string,
  ) => {
    if (!(tname in objectProperties)) objectProperties[tname] = {};
    objectProperties[tname][propertyLabel] = value;
  };

  $: {
    objectProperties = getObjectProperties(formInputs, initialValues, objectProperties);
  }

  $: {
    const result = objectValidationSchema.safeParse(objectProperties);
    if (!result.success) console.error("Bad Input:", result.error); //TODO: correctly warn user
    isFormValid = result.success;
  }

  const findStringValue = (featureName: string) => {
    const value = initialValues[featureName]?.value;
    if (typeof value === "string") {
      return value;
    }
    return "";
  };
</script>

{#each formInputs as feature, i}
  {#if selectedEntityId === "new" || (selectedEntityId !== "new" && feature.sch.group !== "entities")}
    {#if feature.type === "bool"}
      <div class="flex gap-4 items-center">
        <Checkbox
          handleClick={(checked) => handleInputChange(checked, feature.name, feature.sch.name)}
          checked={feature.sch.name in initialValues
            ? initialValues[feature.sch.name][feature.name]?.value === 1
            : false}
        />
        <span class="capitalize">
          {feature.label}
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
        saveValue={(value) => handleInputChange(value, feature.name, feature.sch.name)}
      />
    {/if}
    {#if ["int", "float", "str"].includes(feature.type)}
      <div>
        <span class="capitalize">
          {feature.label}
          {#if feature.required}
            <span>*</span>
          {/if}
        </span>
        {#if feature.type === "str"}
          <AutocompleteTextFeature
            value={findStringValue(feature.name)}
            onTextInputChange={(value) => handleInputChange(value, feature.name, feature.sch.name)}
            featureList={mapFeatureList($itemMetas.featuresList?.objects[feature.name])}
            autofocus={i === 0 && isAutofocusEnabled}
            isInputEnabled={!$itemMetas.featuresList?.objects[feature.name]?.restricted}
          />
        {:else}
          <Input
            type="number"
            step={feature.type === "int" ? "1" : "any"}
            value={feature.sch.name in initialValues
              ? initialValues[feature.sch.name][feature.name]?.value || ""
              : ""}
            autofocus={i === 0}
            on:keyup={(e) => e.stopPropagation()}
            on:input={(e) =>
              handleInputChange(Number(e.currentTarget.value), feature.name, feature.sch.name)}
          />
        {/if}
      </div>
    {/if}
  {/if}
{/each}
