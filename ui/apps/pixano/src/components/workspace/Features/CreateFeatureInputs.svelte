<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Checkbox, Select } from "bits-ui";
  import { CaretUpDown, Check } from "phosphor-svelte";
  import { untrack } from "svelte";

  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";
  import CollectionFeatureInput from "./CollectionFeatureInput.svelte";
  import { itemMetas } from "$lib/stores/workspaceStores.svelte";
  import type { FeatureValues } from "$lib/types/shapeTypes";
  import type { CreateEntityInputs, EntityProperties } from "$lib/types/workspace";
  import { BaseSchema, Input, type ItemFeature } from "$lib/ui";
  import {
    getEntityProperties,
    getValidationSchemaAndFormInputs,
    mapFeatureList,
  } from "$lib/utils/featureMapping";
  import {
    inputsForEntitySelection,
    validateEntityForm,
  } from "$lib/utils/featureValidationSchemas";
  import { getWorkspaceContext } from "$lib/workspace/context";

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
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    formInputs = $bindable([]),
    objectProperties = $bindable({}),
    initialValues = {},
    isAutofocusEnabled = true,
    selectedEntityId = "new",
    baseSchema,
  }: Props = $props();
  const { manifest } = getWorkspaceContext();
  $effect(() => {
    ({ inputs: formInputs } = getValidationSchemaAndFormInputs(manifest, baseSchema));
  });

  const handleInputChange = (value: FeatureValues, propertyLabel: string, tname: string) => {
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

  const activeInputs = $derived(inputsForEntitySelection(formInputs, selectedEntityId));
  const validation = $derived(validateEntityForm(activeInputs, objectProperties));
  $effect(() => {
    isFormValid = validation.success;
  });

  const findStringValue = (table: string, featureName: string) => {
    const value = objectProperties[table]?.[featureName];
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

{#each activeInputs as feature, i}
  {#if feature.type === "bool"}
    <div class="flex gap-4 items-center">
      <Checkbox.Root
        checked={objectProperties[feature.sch.name]?.[feature.name] === true}
        onCheckedChange={(c) => handleInputChange(c, feature.name, feature.sch.name)}
        class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
      >
        {#snippet children({ checked })}
          <span class="flex items-center justify-center text-current h-full w-full">
            {#if checked}
              <Check class="h-3.5 w-3.5" />
            {/if}
          </span>
        {/snippet}
      </Checkbox.Root>
      <span class="text-xs font-medium capitalize text-foreground text-left">
        {feature.label}
        {#if feature.required}
          <span>*</span>
        {/if}
      </span>
    </div>
  {/if}
  {#if feature.type === "collection"}
    <div class="space-y-1">
      <span class="text-xs font-medium text-foreground">
        {feature.label}{feature.required ? " *" : ""}
      </span>
      <CollectionFeatureInput
        value={objectProperties[feature.sch.name]?.[feature.name]}
        itemType={feature.itemType}
        label={feature.label}
        required={feature.required}
        onValueChange={(value) => handleInputChange(value, feature.name, feature.sch.name)}
      />
    </div>
  {/if}
  {#if feature.type === "list"}
    <Select.Root
      type="single"
      onValueChange={(v) => handleInputChange(v, feature.name, feature.sch.name)}
      items={normalizeComboboxItems(feature.options)}
    >
      <Select.Trigger
        class="inline-flex h-10 w-[200px] items-center justify-between rounded-xl border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {#snippet children()}
          {feature.label}
          <CaretUpDown weight="regular" class="ml-2 h-4 w-4 shrink-0 opacity-50" />
        {/snippet}
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          sideOffset={6}
          class="z-50 rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
        >
          {#each normalizeComboboxItems(feature.options) as item}
            <Select.Item
              value={item.value}
              label={item.label}
              class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
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
      <span class="text-xs font-medium capitalize text-foreground text-left">
        {feature.label}
        {#if feature.required}
          <span>*</span>
        {/if}
      </span>
      {#if feature.type === "str"}
        <AutocompleteTextFeature
          value={findStringValue(feature.sch.name, feature.name)}
          onTextInputChange={(value) => handleInputChange(value, feature.name, feature.sch.name)}
          featureList={mapFeatureList(itemMetas.value?.featuresList?.objects?.[feature.name])}
          autofocus={i === 0 && isAutofocusEnabled}
          isInputEnabled={!itemMetas.value?.featuresList?.objects?.[feature.name]?.restricted}
        />
      {:else}
        <Input
          type="number"
          step={feature.type === "int" ? "1" : "any"}
          value={normalizeNumericValue(objectProperties[feature.sch.name]?.[feature.name])}
          autofocus={i === 0}
          onkeyup={(e: KeyboardEvent) => {
            e.stopPropagation();
          }}
          oninput={(e) => {
            handleInputChange(
              (e.currentTarget as HTMLInputElement).value === ""
                ? ""
                : Number((e.currentTarget as HTMLInputElement).value),
              feature.name,
              feature.sch.name,
            );
          }}
        />
      {/if}
    </div>
  {/if}
{/each}

{#if !validation.success}
  <p class="text-xs text-destructive" role="alert">{validation.errors[0]}</p>
{/if}
