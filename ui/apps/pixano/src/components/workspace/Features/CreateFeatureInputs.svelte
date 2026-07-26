<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Checkbox, Select } from "bits-ui";
  import { CaretDown, Check } from "phosphor-svelte";
  import { untrack } from "svelte";

  import AutocompleteTextFeature from "./AutoCompleteFeatureInput.svelte";
  import { itemMetas } from "$lib/stores/workspaceStores.svelte";
  import type { CreateEntityInputs, EntityProperties } from "$lib/types/workspace";
  import { BaseSchema, Input, type ItemFeature } from "$lib/ui";
  import {
    getEntityProperties,
    getValidationSchemaAndFormInputs,
    mapFeatureList,
  } from "$lib/utils/featureMapping";
  import { validateEntityForm, type FieldError } from "$lib/utils/featureValidationSchemas";
  import { humanizeFieldName, humanizeTableName } from "$lib/utils/labels";
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

  let touched = $state<Record<string, boolean>>({});
  let fieldErrors = $state<FieldError[]>([]);

  const fieldKey = (tname: string, name: string) => `${tname}.${name}`;

  const handleInputChange = (
    value: string | number | boolean,
    propertyLabel: string,
    tname: string,
  ) => {
    if (!(tname in objectProperties)) objectProperties[tname] = {};
    objectProperties[tname][propertyLabel] = value;
    touched[fieldKey(tname, propertyLabel)] = true;
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
    fieldErrors = result.fieldErrors;
    isFormValid = result.success;
  });

  function errorFor(tname: string, name: string): string | null {
    if (!touched[fieldKey(tname, name)]) return null;
    return fieldErrors.find((e) => e.sch === tname && e.name === name)?.message ?? null;
  }

  // Fields hidden when linking to an existing object (entity attributes already exist).
  const visibleInputs = $derived(
    formInputs.filter((feature) => selectedEntityId === "new" || feature.sch.group !== "entities"),
  );

  // Group by owning table, preserving first-appearance order; headers only when >1 group
  // (the table context is a heading, never a "[table] field" prefix).
  const groupedInputs = $derived.by(() => {
    const groups: { tname: string; inputs: typeof visibleInputs }[] = [];
    for (const feature of visibleInputs) {
      const group = groups.find((g) => g.tname === feature.sch.name);
      if (group) group.inputs.push(feature);
      else groups.push({ tname: feature.sch.name, inputs: [feature] });
    }
    return groups;
  });
  const showGroupHeaders = $derived(groupedInputs.length > 1);
  const firstFieldKey = $derived(
    visibleInputs.length > 0 ? fieldKey(visibleInputs[0].sch.name, visibleInputs[0].name) : "",
  );

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

  const selectedListValue = (tname: string, name: string): string => {
    const value = objectProperties[tname]?.[name];
    return typeof value === "string" ? value : "";
  };
</script>

{#each groupedInputs as group (group.tname)}
  <div class="flex flex-col gap-3">
    {#if showGroupHeaders}
      <h4 class="text-label text-left">{humanizeTableName(group.tname)}</h4>
    {/if}
    {#each group.inputs as feature (fieldKey(feature.sch.name, feature.name))}
      {@const id = `create-field-${feature.sch.name}-${feature.name}`}
      {@const error = errorFor(feature.sch.name, feature.name)}
      {#if feature.type === "bool"}
        <div class="flex items-center gap-3">
          <Checkbox.Root
            {id}
            checked={feature.sch.name in initialValues
              ? initialValues[feature.sch.name][feature.name]?.value === 1
              : false}
            onCheckedChange={(c) => handleInputChange(c === true, feature.name, feature.sch.name)}
            class="peer h-4 w-4 shrink-0 rounded border border-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
          >
            {#snippet children({ checked })}
              <span class="flex items-center justify-center text-current h-full w-full">
                {#if checked}
                  <Check class="h-3.5 w-3.5" />
                {/if}
              </span>
            {/snippet}
          </Checkbox.Root>
          <label for={id} class="cursor-pointer select-none text-sm text-foreground">
            {humanizeFieldName(feature.name)}{#if feature.required}<span class="text-destructive">
                *
              </span>{/if}
          </label>
        </div>
      {:else}
        <div class="flex flex-col gap-1.5">
          <label for={id} class="text-xs font-medium text-foreground text-left">
            {humanizeFieldName(feature.name)}{#if feature.required}<span class="text-destructive">
                *
              </span>{/if}
          </label>
          {#if feature.type === "list"}
            <Select.Root
              type="single"
              value={selectedListValue(feature.sch.name, feature.name)}
              onValueChange={(v) => handleInputChange(v, feature.name, feature.sch.name)}
              items={normalizeComboboxItems(feature.options)}
            >
              <Select.Trigger
                {id}
                class="inline-flex h-10 w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 text-sm shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {#snippet children()}
                  <span
                    class="truncate {selectedListValue(feature.sch.name, feature.name) === ''
                      ? 'text-muted-foreground/60'
                      : ''}"
                  >
                    {selectedListValue(feature.sch.name, feature.name) || "Choose…"}
                  </span>
                  <CaretDown size={13} class="shrink-0 text-muted-foreground" />
                {/snippet}
              </Select.Trigger>
              <Select.Portal>
                <Select.Content
                  sideOffset={6}
                  class="z-50 max-h-64 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
                >
                  {#each normalizeComboboxItems(feature.options) as item (item.value)}
                    <Select.Item
                      value={item.value}
                      label={item.label}
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                    >
                      <Check
                        size={13}
                        class={selectedListValue(feature.sch.name, feature.name) === item.value
                          ? "text-primary"
                          : "text-transparent"}
                      />
                      {item.label}
                    </Select.Item>
                  {/each}
                </Select.Content>
              </Select.Portal>
            </Select.Root>
          {:else if feature.type === "str"}
            <AutocompleteTextFeature
              value={findStringValue(feature.name)}
              onTextInputChange={(value) =>
                handleInputChange(value, feature.name, feature.sch.name)}
              featureList={mapFeatureList(itemMetas.value?.featuresList?.objects?.[feature.name])}
              autofocus={isAutofocusEnabled &&
                firstFieldKey === fieldKey(feature.sch.name, feature.name)}
              isInputEnabled={!itemMetas.value?.featuresList?.objects?.[feature.name]?.restricted}
            />
          {:else}
            <Input
              {id}
              type="number"
              step={feature.type === "int" ? "1" : "any"}
              class="w-full"
              value={feature.sch.name in initialValues
                ? normalizeNumericValue(initialValues[feature.sch.name][feature.name]?.value)
                : ""}
              onkeyup={(e: KeyboardEvent) => {
                e.stopPropagation();
              }}
              oninput={(e) => {
                handleInputChange(
                  Number((e.currentTarget as HTMLInputElement).value),
                  feature.name,
                  feature.sch.name,
                );
              }}
            />
          {/if}
          {#if error}
            <p class="text-xs text-destructive text-left">{error}</p>
          {/if}
        </div>
      {/if}
    {/each}
  </div>
{/each}
