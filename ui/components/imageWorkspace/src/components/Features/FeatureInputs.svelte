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

  import { Checkbox } from "@pixano/core/src";
  import type { Feature } from "../../lib/types/imageWorkspaceTypes";

  import FeatureTextInput from "./TextInputFeature.svelte";
  import ListFeature from "./ListInputFeature.svelte";

  export let features: Feature[];
  export let feature_class: string;

  export let isEditing: boolean;
  export let saveInputChange: (value: string | boolean | number, propertyName: string) => void;
</script>

{#each features as feature}
  <div class="grid gap-4 grid-cols-[150px_auto] mt-2">
    {#if isEditing || feature.value !== undefined}
      <p class="font-medium first-letter:uppercase">{feature.label.replace("_", " ")}</p>
    {/if}

    {#if feature.type === "bool" && (feature.value !== undefined || isEditing)}
      <Checkbox
        checked={!!feature.value}
        disabled={!isEditing}
        handleClick={(checked) => saveInputChange(checked, feature.name)}
      />
    {/if}
    {#if feature.type === "list"}
      <ListFeature
        handleInputChange={(value, name) => saveInputChange(value, name)}
        {isEditing}
        listFeature={{ value: feature.value, name: feature.name, options: feature.options }}
      />
    {/if}
    {#if feature.type === "str" || feature.type === "int" || feature.type === "float"}
      <FeatureTextInput
        {feature_class}
        saveInputChange={(value, name) => saveInputChange(value, name)}
        textFeature={{ value: feature.value, name: feature.name }}
        inputType={feature.type}
        {isEditing}
      />
    {/if}
  </div>
{/each}
