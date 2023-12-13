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

  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import type { ItemObject } from "@pixano/core";

  import { objectSetup } from "../../lib/settings/objectValidationSchemas";
  import type { Feature } from "../../lib/types/imageWorkspaceTypes";

  import FeatureTextInput from "./TextInputFeature.svelte";
  import ListFeature from "./ListInputFeature.svelte";

  export let features: ItemObject["features"];
  export let isEditing: boolean;
  export let saveInputChange: (value: string | boolean, propertyName: string) => void;

  $: featuresWithValue = objectSetup
    .map((property) => {
      const value = features[property.name]?.value;
      return {
        ...property,
        label: property.label,
        name: property.name,
        value,
      };
    })
    .filter(Boolean) as Feature[];
</script>

{#each featuresWithValue as feature}
  <div class="mt-1">
    {#if isEditing || feature.value !== undefined}
      <p class="font-medium pb-1">{feature.label}</p>
    {/if}
    {#if feature.type === "boolean" && (feature.value !== undefined || isEditing)}
      <Checkbox
        checked={feature.value}
        disabled={!isEditing}
        handleClick={(checked) => saveInputChange(checked, feature.name)}
      />
    {/if}
    {#if feature.type === "list"}
      <ListFeature
        handleInputChange={(value, name) => saveInputChange(value, name)}
        {isEditing}
        listFeature={{ value: feature.value, name: feature.name }}
      />
    {/if}
    {#if feature.type === "text" || feature.type === "number"}
      <FeatureTextInput
        saveInputChange={(value, name) => saveInputChange(value, name)}
        textFeature={{ value: feature.value, name: feature.name }}
        inputType={feature.type}
        {isEditing}
      />
    {/if}
  </div>
{/each}
