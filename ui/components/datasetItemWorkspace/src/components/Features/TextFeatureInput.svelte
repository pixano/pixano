<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { CheckCheckIcon } from "lucide-svelte";

  import { Annotation, Entity, Item } from "@pixano/core";
  import { Input, type FeaturesValues } from "@pixano/core/src";

  import { addNewInput, mapFeatureList } from "../../lib/api/featuresApi";
  import { itemMetas } from "../../lib/stores/datasetItemWorkspaceStores";
  import type { NumberFeature, TextFeature } from "../../lib/types/datasetItemWorkspaceTypes";
  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";

  export let feature: TextFeature | NumberFeature;
  export let isEditing: boolean;
  export let saveInputChange: (
    value: string | number,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => void;
  export let featureClass: keyof FeaturesValues;

  let isSaved = false;

  const onTextInputChange = (
    value: string,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => {
    let formattedValue: string | number = value;
    if (feature.type === "int") {
      formattedValue = Math.round(Number(value));
    } else if (feature.type === "float") {
      formattedValue = Number(value);
    }

    if (typeof formattedValue === "string") {
      addNewInput($itemMetas.featuresList, featureClass, propertyName, formattedValue);
    }
    saveInputChange(formattedValue, propertyName, obj);
    isSaved = true;
  };
</script>

<div class="flex justify-start items-center gap-4 overflow-hidden">
  {#if isEditing}
    {#if feature.type === "str"}
      <AutocompleteTextFeature
        value={feature.value}
        onTextInputChange={(value) => onTextInputChange(value, feature.name, feature.obj)}
        featureList={mapFeatureList($itemMetas.featuresList?.[featureClass][feature.name])}
        isInputEnabled={!$itemMetas.featuresList?.[featureClass][feature.name]?.restricted}
      />
    {:else}
      <Input
        value={feature.value}
        type="number"
        step={feature.type === "int" ? "1" : "any"}
        on:change={(e) => onTextInputChange(e.currentTarget.value, feature.name, feature.obj)}
        on:input={() => (isSaved = false)}
        on:keyup={(e) => e.stopPropagation()}
      />
    {/if}
    {#if isSaved}
      <span class="text-green-700">
        <CheckCheckIcon />
      </span>
    {/if}
  {:else if feature.value || feature.value === 0}
    <span class="block truncate text-foreground font-medium" title={`${feature.value}`}>
      {feature.value}
    </span>
  {/if}
</div>
