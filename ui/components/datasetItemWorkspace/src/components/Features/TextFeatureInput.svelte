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

  import { CheckCheckIcon } from "lucide-svelte";

  import { Input, type FeaturesValues } from "@pixano/core/src";

  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";
  import type { TextFeature, NumberFeature } from "../../lib/types/datasetItemWorkspaceTypes";
  import { itemMetas } from "../../lib/stores/datasetItemWorkspaceStores";
  import { addNewInput, mapFeatureList } from "../../lib/api/featuresApi";

  export let feature: TextFeature | NumberFeature;
  export let isEditing: boolean;
  export let saveInputChange: (value: string | number, propertyName: string) => void;
  export let featureClass: keyof FeaturesValues;

  let isSaved = false;

  const onTextInputChange = (value: string, propertyName: string) => {
    let formattedValue: string | number = value;
    if (feature.type === "int") {
      formattedValue = Math.round(Number(value));
    } else if (feature.type === "float") {
      formattedValue = Number(value);
    }

    if (typeof formattedValue === "string") {
      addNewInput($itemMetas.featuresList, featureClass, propertyName, formattedValue);
    }
    saveInputChange(formattedValue, propertyName);
    isSaved = true;
  };
</script>

<div class="flex justify-start items-center gap-4">
  {#if isEditing}
    {#if feature.type === "str"}
      <AutocompleteTextFeature
        value={feature.value}
        onTextInputChange={(value) => onTextInputChange(value, feature.name)}
        featureList={mapFeatureList($itemMetas.featuresList?.[featureClass][feature.name])}
        isFixed={isEditing && featureClass === "objects"}
      />
    {:else}
      <Input
        value={feature.value}
        type="number"
        step={feature.type === "int" ? "1" : "any"}
        on:change={(e) => onTextInputChange(e.currentTarget.value, feature.name)}
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
    <p class="first-letter:uppercase">
      {feature.value}
    </p>
  {/if}
</div>
