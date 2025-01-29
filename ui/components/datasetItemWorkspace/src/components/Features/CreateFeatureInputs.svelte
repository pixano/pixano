<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { BaseSchema, Message, TextSpan, type ItemFeature } from "@pixano/core";
  import {
    BBox,
    Checkbox,
    Combobox,
    Entity,
    Input,
    Keypoints,
    Mask,
    Track,
    Tracklet,
  } from "@pixano/core/src";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { itemMetas } from "../../lib/stores/datasetItemWorkspaceStores";

  import {
    createObjectInputsSchema,
    createSchemaFromFeatures,
    type InputFeatures,
  } from "../../lib/settings/objectValidationSchemas";
  import type {
    CreateObjectInputs,
    CreateObjectSchema,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";
  //import { defaultObjectFeatures } from "../../lib/settings/defaultFeatures";
  import { mapFeatureList } from "../../lib/api/featuresApi";

  export let isFormValid: boolean = false;
  export let formInputs: CreateObjectInputs = [];
  export let objectProperties: ObjectProperties = {};
  export let initialValues: Record<string, Record<string, ItemFeature>> = {};
  export let isAutofocusEnabled: boolean = true;
  export let entitiesCombo: { id: string; name: string }[] = [{ id: "new", name: "New" }];
  export let selectedEntityId: string = entitiesCombo[0].id;
  export let baseSchema: BaseSchema;
  let objectValidationSchema: CreateObjectSchema;

  datasetSchema.subscribe((schema) => {
    //TODO: need to take schema relation into account (when schema relation available)
    //required when there is several differents tracks / entities / subentities for different purpose
    let featuresArray: InputFeatures = [];
    Object.entries(schema?.schemas ?? {}).forEach(([tname, sch]) => {
      let nonFeatsFields: string[] = [];
      let group = "entities";
      if ([BaseSchema.Entity, BaseSchema.Track, baseSchema].includes(sch.base_schema)) {
        if (sch.base_schema === BaseSchema.Entity) {
          nonFeatsFields = nonFeatsFields.concat(Entity.nonFeaturesFields());
        }
        if (sch.base_schema === BaseSchema.Track) {
          nonFeatsFields = nonFeatsFields.concat(Track.nonFeaturesFields());
        }
        if (baseSchema === sch.base_schema) {
          group = "annotations";
          if (baseSchema === BaseSchema.BBox)
            nonFeatsFields = nonFeatsFields.concat(BBox.nonFeaturesFields());
          if (baseSchema === BaseSchema.Keypoints)
            nonFeatsFields = nonFeatsFields.concat(Keypoints.nonFeaturesFields());
          if (baseSchema === BaseSchema.Mask)
            nonFeatsFields = nonFeatsFields.concat(Mask.nonFeaturesFields());
          if (baseSchema === BaseSchema.Tracklet)
            nonFeatsFields = nonFeatsFields.concat(Tracklet.nonFeaturesFields());
          if (baseSchema === BaseSchema.TextSpan)
            nonFeatsFields = nonFeatsFields.concat(TextSpan.nonFeaturesFields());
          if (baseSchema === BaseSchema.Message)
            nonFeatsFields = nonFeatsFields.concat(Message.nonFeaturesFields());
        }
        //TODO: custom fields from other types
        for (const feat in sch.fields) {
          if (!nonFeatsFields.includes(feat)) {
            if (["int", "float", "str", "bool"].includes(sch.fields[feat].type)) {
              featuresArray.push({
                name: feat,
                required: false, //TODO (info not in datasetSchema (nowhere yet))
                label: feat,
                type: sch.fields[feat].type as "int" | "float" | "str" | "bool",
                sch: { name: tname, group, base_schema: sch.base_schema },
              });
            }
            if ("list" === sch.fields[feat].type) {
              featuresArray.push({
                name: feat,
                required: false, //TODO (info not in datasetSchema (nowhere yet))
                label: feat,
                type: "list",
                options: [], //TODO for list type (not covered yet)
                sch: { name: tname, group, base_schema: sch.base_schema },
              });
            }
          }
        }
      }
    });
    objectValidationSchema = createSchemaFromFeatures(featuresArray);
    formInputs = createObjectInputsSchema.parse(featuresArray);
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
    for (const feat of formInputs) {
      if (feat.sch.name in initialValues && feat.name in initialValues[feat.sch.name]) {
        if (typeof initialValues[feat.sch.name][feat.name].value !== "object") {
          if (!(feat.sch.name in objectProperties)) objectProperties[feat.sch.name] = {};
          if (!(feat.name in objectProperties[feat.sch.name])) {
            objectProperties[feat.sch.name][feat.name] = initialValues[feat.sch.name][feat.name]
              .value as string | number | boolean;
          }
        }
      } else {
        if (!(feat.sch.name in objectProperties)) objectProperties[feat.sch.name] = {};
        if (!(feat.name in objectProperties[feat.sch.name])) {
          if (feat.type === "bool") objectProperties[feat.sch.name][feat.name] = false;
          if (feat.type === "str") objectProperties[feat.sch.name][feat.name] = "";
          if (feat.type === "int" || feat.type === "float")
            objectProperties[feat.sch.name][feat.name] = 0;
          if (feat.type === "list") objectProperties[feat.sch.name][feat.name] = ""; //TODO list case... ??
        }
      }
    }
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

{#if entitiesCombo.length > 0}
  <span>Select parent entity</span>
  <select
    class="py-1 px-2 border rounded focus:outline-none
bg-slate-100 border-slate-300 focus:border-main"
    bind:value={selectedEntityId}
  >
    {#each entitiesCombo as { id, name }}
      <option value={id}>
        {name}
      </option>
    {/each}
  </select>
{/if}

{#each formInputs as feature, i}
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
{/each}
