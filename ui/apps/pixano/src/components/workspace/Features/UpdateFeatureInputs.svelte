<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Checkbox } from "bits-ui";
  import { Check } from "lucide-svelte";

  import { Annotation, Entity, Item, type FeaturesValues } from "$lib/ui";

  import type { Feature } from "$lib/types/workspace";
  import ListFeature from "./SelectFeatureInput.svelte";
  import FeatureTextInput from "./TextFeatureInput.svelte";


  interface Props {
    features: Feature[];
    featureClass: keyof FeaturesValues;
    isEditing: boolean;
    saveInputChange: (
    value: string | boolean | number,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => void;
  }

  let {
    features,
    featureClass,
    isEditing,
    saveInputChange
  }: Props = $props();
</script>

{#each features as feature}
  <div
    class="flex w-full items-center justify-between py-1.5 px-2 rounded-md hover:bg-accent/50 transition-colors duration-100 min-h-[32px]"
  >
    {#if isEditing || feature.value !== undefined}
      <span class="text-[13px] text-muted-foreground truncate max-w-[45%]" title={feature.obj.id}>
        {feature.label.replace("_", " ")}
      </span>
    {/if}
    <div class="flex items-center justify-end overflow-hidden max-w-[50%] text-[13px]">
      {#if feature.type === "bool" && (feature.value !== undefined || isEditing)}
        <Checkbox.Root
          checked={!!feature.value}
          disabled={!isEditing}
          onCheckedChange={(checked) => saveInputChange(checked, feature.name, feature.obj)}
          class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
        >
          {#snippet children({ checked })}
            <span class="flex items-center justify-center text-current h-full w-full">
              {#if checked}
                <Check class="h-3.5 w-3.5" strokeWidth={3} />
              {/if}
            </span>
          {/snippet}
        </Checkbox.Root>
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
