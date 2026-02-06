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
  <div class="flex w-full items-center justify-between py-1.5 px-2 rounded-md hover:bg-accent/50 transition-colors duration-100 min-h-[32px]">
    {#if isEditing || feature.value !== undefined}
      <span class="text-[13px] text-muted-foreground truncate max-w-[45%]" title={feature.obj.id}>
        {feature.label.replace("_", " ")}
      </span>
    {/if}
    <div class="flex items-center justify-end overflow-hidden max-w-[50%] text-[13px]">
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
  </div>
{/each}
