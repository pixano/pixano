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

  import { Input } from "@pixano/core/src";
  import type { TextFeature, NumberFeature } from "../../lib/types/imageWorkspaceTypes";
  import { itemFeaturesAvailableValues } from "../../lib/stores/imageWorkspaceStores";

  export let textFeature: Pick<NumberFeature | TextFeature, "name" | "value">;
  export let isEditing: boolean;
  export let saveInputChange: (value: string | number, propertyName: string) => void;
  export let inputType: NumberFeature["type"] | TextFeature["type"] = "str";
  export let feature_class: string;

  let isSaved = false;

  const onTextInputChange = (value: string, propertyName: string) => {
    let formattedValue: string | number = value;
    if (inputType === "int") {
      formattedValue = Math.round(Number(value));
    } else if (inputType === "float") {
      formattedValue = Number(value);
    }

    // add new inputs to lists of available values
    if (feature_class in $itemFeaturesAvailableValues) {
      if (typeof formattedValue === "string") {
        if (!$itemFeaturesAvailableValues[feature_class][propertyName]) {
          $itemFeaturesAvailableValues[feature_class][propertyName] = [formattedValue];
        } else if (!$itemFeaturesAvailableValues[feature_class][propertyName].includes(formattedValue)) {
          $itemFeaturesAvailableValues[feature_class][propertyName].push(formattedValue);
        }
      }
    }

    saveInputChange(formattedValue, propertyName);
    isSaved = true;
  };
</script>

<div class="flex justify-start items-center gap-4">
  {#if isEditing}
    <Input
      value={textFeature.value}
      type={inputType === "str" ? "text" : "number"}
      step={inputType === "int" ? "1" : "any"}
      list="{feature_class}_availableValues_{textFeature.name}"
      on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
      on:input={() => (isSaved = false)}
      on:keyup={(e) => e.stopPropagation()}
    />
    <datalist id="{feature_class}_availableValues_{textFeature.name}">
      {#if feature_class in $itemFeaturesAvailableValues && textFeature.name in $itemFeaturesAvailableValues[feature_class]}
        {#each $itemFeaturesAvailableValues[feature_class][textFeature.name].sort() as proposedValue}
          <option value={proposedValue} />
        {/each}
      {/if}
    </datalist>

    {#if isSaved}
      <span class="text-green-700">
        <CheckCheckIcon />
      </span>
    {/if}
  {:else if textFeature.value || textFeature.value === 0}
    <p class="first-letter:uppercase">
      {textFeature.value}
    </p>
  {/if}
</div>
