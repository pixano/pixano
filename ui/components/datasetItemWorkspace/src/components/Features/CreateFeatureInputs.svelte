<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Input, Checkbox, Combobox, Entity, Track } from "@pixano/core/src";
  import type { FeatureValues, ItemFeature } from "@pixano/core";

  import { itemMetas } from "../../lib/stores/datasetItemWorkspaceStores";
  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";

  import {
    createObjectInputsSchema,
    createSchemaFromFeatures,
    type InputFeatures,
  } from "../../lib/settings/objectValidationSchemas";
  import type {
    CreateObjectInputs,
    CreateObjectSchema,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";

  //import { defaultObjectFeatures } from "../../lib/settings/defaultFeatures";
  import { mapFeatureList } from "../../lib/api/featuresApi";

  export let isFormValid: boolean = false;
  export let formInputs: CreateObjectInputs = [];
  export let objectProperties: { [key: string]: FeatureValues } = {};
  export let initialValues: Record<string, ItemFeature> = {};
  export let isAutofocusEnabled: boolean = true;

  let objectValidationSchema: CreateObjectSchema;

  datasetSchema.subscribe((schema) => {
    let featuresArray: InputFeatures = [];
    Object.values(schema.schemas).forEach((sch) => {
      let nonFeatsFields: string[] = [];
      if (["Entity", "Track"].includes(sch.base_schema)) {
        if ("Entity" === sch.base_schema) {
          nonFeatsFields = nonFeatsFields.concat(Entity.nonFeaturesFields());
        }
        if ("Track" === sch.base_schema) {
          nonFeatsFields = nonFeatsFields.concat(Track.nonFeaturesFields());
        }
        //TODO: custom fields from other types
        for (const feat in sch.fields) {
          if (!nonFeatsFields.includes(feat)) {
            if (["int", "float", "str", "bool", "list"].includes(sch.fields[feat].type)) {
              featuresArray.push({
                name: feat,
                required: false, //TODO (info not in datasetSchema (nowhere yet))
                label: feat,
                type: sch.fields[feat].type as "int" | "float" | "str" | "bool",
              });
            }
            if ("list" === sch.fields[feat].type) {
              featuresArray.push({
                name: feat,
                required: false, //TODO (info not in datasetSchema (nowhere yet))
                label: feat,
                type: "list",
                options: [], //TODO for list type (not covered yet)
              });
            }
          }
        }
      }
    });
    objectValidationSchema = createSchemaFromFeatures(featuresArray);
    formInputs = createObjectInputsSchema.parse(featuresArray);
  });

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
      {#if feature.type === "str"}
        <AutocompleteTextFeature
          value={findStringValue(feature.name)}
          onTextInputChange={(value) => handleInputChange(value, feature.name)}
          featureList={mapFeatureList($itemMetas.featuresList?.objects[feature.name])}
          autofocus={i === 0 && isAutofocusEnabled}
          isInputEnabled={!$itemMetas.featuresList?.objects[feature.name]?.restricted}
        />
      {:else}
        <Input
          type="number"
          step={feature.type === "int" ? "1" : "any"}
          value={initialValues[feature.name]?.value || ""}
          autofocus={i === 0}
          on:keyup={(e) => e.stopPropagation()}
          on:input={(e) => handleInputChange(Number(e.currentTarget.value), feature.name)}
        />
      {/if}
    </div>
  {/if}
{/each}
