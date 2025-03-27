<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Annotation, Entity, Item } from "@pixano/core";
  import { Checkbox, type FeaturesValues } from "@pixano/core/src";

  import type { Feature } from "../../lib/types/datasetItemWorkspaceTypes";
  import ListFeature from "./SelectFeatureInput.svelte";
  import FeatureTextInput from "./TextFeatureInput.svelte";

  export let features: Feature[];
  export let featureClass: keyof FeaturesValues;

  export let isEditing: boolean;
  export let saveInputChange: (
    value: string | boolean | number,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => void;
</script>

{#each features as feature}
  <div class="flex w-full gap-4 mt-2 px-4">
    {#if isEditing || feature.value !== undefined}
      <p class="capitalize flex items-center">
        {feature.label.replace("_", " ")}
      </p>
    {/if}
    {#if feature.type === "bool" && (feature.value !== undefined || isEditing)}
      <Checkbox
        checked={!!feature.value}
        disabled={!isEditing}
        handleClick={(checked) => saveInputChange(checked, feature.name, feature.obj)}
      />
    {/if}
    {#if feature.type === "list"}
      <ListFeature
        {isEditing}
        handleInputChange={(value, name) => saveInputChange(value, name, feature.obj)}
        listFeature={{ value: feature.value, name: feature.name, options: feature.options }}
      />
    {/if}
    {#if feature.type === "str" || feature.type === "int" || feature.type === "float"}
      <FeatureTextInput {featureClass} {feature} {saveInputChange} {isEditing} />
    {/if}
  </div>
{/each}
