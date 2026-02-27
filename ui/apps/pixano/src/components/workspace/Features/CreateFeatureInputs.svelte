<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  
  // Imports
  import { untrack } from "svelte";

  import { Checkbox, Select } from "bits-ui";
  import { Check, CaretUpDown } from "phosphor-svelte";

  import { BaseSchema, Input, type ItemFeature } from "$lib/ui";

  import { datasetSchema } from "$lib/stores/appStores.svelte";
  import {
    getEntityProperties,
    getValidationSchemaAndFormInputs,
    mapFeatureList,
  } from "$lib/utils/featureMapping";
  import { validateEntityForm } from "$lib/utils/featureValidationSchemas";
  import { itemMetas } from "$lib/stores/workspaceStores.svelte";
  import type {
    CreateEntityInputs,
    EntityProperties,
  } from "$lib/types/workspace";
  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";

  interface Props {
    isFormValid?: boolean;
    formInputs?: CreateEntityInputs;
    objectProperties?: EntityProperties;
    initialValues?: Record<string, Record<string, ItemFeature>>;
    isAutofocusEnabled?: boolean;
    selectedEntityId?: string;
    baseSchema: BaseSchema;
  }

  let {
    isFormValid = $bindable(false),
    formInputs = $bindable([]),
    objectProperties = $bindable({}),
    initialValues = {},
    isAutofocusEnabled = true,
    selectedEntityId = "new",
    baseSchema
  }: Props = $props();
  $effect(() => {
    const schema = datasetSchema.value;
    ({ inputs: formInputs } = getValidationSchemaAndFormInputs(schema, baseSchema));
  });

  const handleInputChange = (
    value: string | number | boolean,
    propertyLabel: string,
    tname: string,
  ) => {
    if (!(tname in objectProperties)) objectProperties[tname] = {};
    objectProperties[tname][propertyLabel] = value;
  };

  $effect(() => {
    const inputs = formInputs;
    const initial = initialValues;
    untrack(() => {
      getEntityProperties(inputs, initial, objectProperties);
    });
  });

  $effect(() => {
    const result = validateEntityForm(formInputs, objectProperties);
    if (!result.success) console.error("Bad Input:", result.errors); //TODO: correctly warn user
    isFormValid = result.success;
  });

  const findStringValue = (featureName: string) => {
    const value = initialValues[featureName]?.value;
    if (typeof value === "string") {
      return value;
    }
    return "";
  };

  const normalizeComboboxItems = (items?: Array<{ value?: string; label?: string }>) =>
    (items ?? []).map((item) => ({
      value: item.value ?? "",
      label: item.label ?? item.value ?? "",
    }));

  const normalizeNumericValue = (value: unknown): string | number => {
    if (typeof value === "string" || typeof value === "number") return value;
    return "";
  };
</script>

{#each formInputs as feature, i}
  {#if selectedEntityId === "new" || (selectedEntityId !== "new" && feature.sch.group !== "entities")}
    {#if feature.type === "bool"}
      <div class="flex gap-4 items-center">
        <Checkbox.Root
          checked={feature.sch.name in initialValues
            ? initialValues[feature.sch.name][feature.name]?.value === 1
            : false}
          onCheckedChange={(c) => handleInputChange(c, feature.name, feature.sch.name)}
          class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
        >
          {#snippet children({ checked })}
            <span class="flex items-center justify-center text-current h-full w-full">
              {#if checked}
                <Check class="h-3.5 w-3.5"  />
              {/if}
            </span>
          {/snippet}
        </Checkbox.Root>
        <span class="capitalize">
          {feature.label}
          {#if feature.required}
            <span>*</span>
          {/if}
        </span>
      </div>
    {/if}
    {#if feature.type === "list"}
      <Select.Root
        type="single"
        onValueChange={(v) => handleInputChange(v, feature.name, feature.sch.name)}
        items={normalizeComboboxItems(feature.options)}
      >
        <Select.Trigger
          class="justify-between h-10 px-4 py-2 border border-input rounded-md bg-background text-sm inline-flex items-center w-[200px]"
        >
          {#snippet children()}
            {feature.label}
            <CaretUpDown weight="regular" class="ml-2 h-4 w-4 shrink-0 opacity-50" />
          {/snippet}
        </Select.Trigger>
        <Select.Portal>
          <Select.Content
            class="z-50 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
          >
            {#each normalizeComboboxItems(feature.options) as item}
              <Select.Item
                value={item.value}
                label={item.label}
                class="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm cursor-pointer data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
              >
                <Check class="h-4 w-4 text-transparent" />
                {item.label}
              </Select.Item>
            {/each}
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    {/if}
    {#if ["int", "float", "str"].includes(feature.type)}
      <div>
        <span class="capitalize">
          {feature.label}
          {#if feature.required}
            <span>*</span>
          {/if}
        </span>
        {#if feature.type === "str"}
          <AutocompleteTextFeature
            value={findStringValue(feature.name)}
            onTextInputChange={(value) => handleInputChange(value, feature.name, feature.sch.name)}
            featureList={mapFeatureList(itemMetas.value?.featuresList?.objects?.[feature.name])}
            autofocus={i === 0 && isAutofocusEnabled}
            isInputEnabled={!itemMetas.value?.featuresList?.objects?.[feature.name]?.restricted}
          />
        {:else}
          <Input
            type="number"
            step={feature.type === "int" ? "1" : "any"}
            value={feature.sch.name in initialValues
              ? normalizeNumericValue(initialValues[feature.sch.name][feature.name]?.value)
              : ""}
            autofocus={i === 0}
            onkeyup={(e) => e.stopPropagation()}
            oninput={(e) =>
              handleInputChange(
                Number((e.currentTarget as HTMLInputElement).value),
                feature.name,
                feature.sch.name,
              )}
          />
        {/if}
      </div>
    {/if}
  {/if}
{/each}
