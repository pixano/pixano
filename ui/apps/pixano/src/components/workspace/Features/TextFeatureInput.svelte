<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Checks } from "phosphor-svelte";

  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";
  import { itemMetas } from "$lib/stores/workspaceStores.svelte";
  import type { NumberFeature, TextFeature } from "$lib/types/workspace";
  import { Annotation, Entity, Input, Item, type FeaturesValues } from "$lib/ui";
  import { addNewInput, mapFeatureList } from "$lib/utils/featureMapping";
  import { validateEntityForm } from "$lib/utils/featureValidationSchemas";

  interface Props {
    feature: TextFeature | NumberFeature;
    isEditing: boolean;
    saveInputChange: (
      value: string | number,
      propertyName: string,
      obj: Item | Entity | Annotation,
    ) => void;
    featureClass: keyof FeaturesValues;
  }

  let { feature, isEditing, saveInputChange, featureClass }: Props = $props();

  let isSaved = $state(false);
  let error = $state("");
  $effect(() => {
    if (!isEditing) {
      error = "";
      isSaved = false;
    }
  });

  const onTextInputChange = (
    value: string,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => {
    let formattedValue: string | number = value;
    if (feature.type === "int" || feature.type === "float") {
      formattedValue = value.trim() === "" ? "" : Number(value);
    }

    const validation = validateEntityForm([feature], {
      [feature.sch.name]: { [feature.name]: formattedValue },
    });
    error = validation.errors[0] ?? "";
    if (!validation.success) return;

    if (typeof formattedValue === "string") {
      addNewInput(itemMetas.value?.featuresList, featureClass, propertyName, formattedValue);
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
        featureList={mapFeatureList(itemMetas.value?.featuresList?.[featureClass]?.[feature.name])}
        isInputEnabled={!itemMetas.value?.featuresList?.[featureClass]?.[feature.name]?.restricted}
      />
    {:else}
      <Input
        value={feature.value}
        type="number"
        step={feature.type === "int" ? "1" : "any"}
        onchange={(e) =>
          onTextInputChange((e.currentTarget as HTMLInputElement).value, feature.name, feature.obj)}
        oninput={() => {
          isSaved = false;
        }}
        onkeyup={(e: KeyboardEvent) => {
          e.stopPropagation();
        }}
      />
    {/if}
    {#if isSaved}
      <span class="text-success">
        <Checks weight="regular" />
      </span>
    {/if}
  {:else if feature.value || feature.value === 0}
    <span class="block truncate text-foreground font-medium" title={`${feature.value}`}>
      {feature.value}
    </span>
  {/if}
</div>
{#if error}
  <p class="text-xs text-destructive" role="alert">{error}</p>
{/if}
