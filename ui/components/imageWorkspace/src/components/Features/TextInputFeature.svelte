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

  // import { Input } from "@pixano/core/src";

  import AutocompleteTextFeature from "./AutoCompleteFeature.svelte";
  import type { TextFeature, NumberFeature } from "../../lib/types/imageWorkspaceTypes";
  import {
    datasetsStore,
    currentDatasetIdStore,
  } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  // import { addNewInput } from "../../lib/api/featuresApi";

  export let textFeature: Pick<NumberFeature | TextFeature, "name" | "value">;
  export let isEditing: boolean;
  // export let saveInputChange: (value: string | number, propertyName: string) => void;
  // export let inputType: NumberFeature["type"] | TextFeature["type"] = "str";
  // export let feature_class: string;

  let isSaved = false;

  $: featuresValues = $datasetsStore.find(
    (ds) => ds.id === $currentDatasetIdStore,
  )?.features_values;

  // const onTextInputChange = (value: string, propertyName: string) => {
  //   let formattedValue: string | number = value;
  //   if (inputType === "int") {
  //     formattedValue = Math.round(Number(value));
  //   } else if (inputType === "float") {
  //     formattedValue = Number(value);
  //   }

  //   if (typeof formattedValue === "string") {
  //     addNewInput(
  //       $datasetsStore.find((ds) => ds.id === $currentDatasetIdStore)?.features_values,
  //       feature_class,
  //       propertyName,
  //       formattedValue,
  //     );
  //   }

  //   saveInputChange(formattedValue, propertyName);
  //   isSaved = true;
  // };

  $: listItems = featuresValues?.scene[textFeature.name].map((feature) => ({
    label: feature,
    value: feature,
  }));
</script>

<div class="flex justify-start items-center gap-4 flex-col">
  {#if isEditing}
    <!-- <Input
      value={textFeature.value}
      type={inputType === "str" ? "text" : "number"}
      step={inputType === "int" ? "1" : "any"}
      list="{feature_class}_availableValues_{textFeature.name}"
      on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
      on:input={() => (isSaved = false)}
      on:keyup={(e) => e.stopPropagation()}
    /> -->
    <AutocompleteTextFeature {listItems} />

    <!-- <datalist id="{feature_class}_availableValues_{textFeature.name}">
      {#if feature_class === "objects"}
        {#if featuresValues?.objects && textFeature.name in featuresValues.objects}
          {#each featuresValues.objects[textFeature.name].sort() as proposedValue}
            <option value={proposedValue} />
          {/each}
        {/if}
      {:else if feature_class === "scene"}
        {#if featuresValues?.scene && textFeature.name in featuresValues.scene}
          {#each featuresValues.scene[textFeature.name].sort() as proposedValue}
            <option value={proposedValue} />
          {/each}
        {/if}
      {/if}
    </datalist> -->

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
