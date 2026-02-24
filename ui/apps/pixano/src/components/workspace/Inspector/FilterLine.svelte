<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { untrack } from "svelte";

  import { Checkbox } from "bits-ui";
  import { Check } from "lucide-svelte";

  import { IconButton } from "$lib/ui";

  import {
    getOperatorsForType,
    type FieldCol,
    type FieldOperator,
    type EntityFilter,
  } from "$lib/types/workspace";

  interface Props {
    filter: EntityFilter;
    tableColumns: string[];
    fieldColumns: Record<string, FieldCol[]>;
  }

  let { filter = $bindable(), tableColumns, fieldColumns }: Props = $props();

  let ftype: string = $state("");

  $effect(() => {
    untrack(handleTableChange);
  });

  let fieldOperators: FieldOperator[] = $state([]);

  const handleTableChange = () => {
    filter.name = fieldColumns[filter.table][0].name;
    handleFieldChange();
  };

  const handleFieldChange = () => {
    ftype = fieldColumns[filter.table].find((field) => field.name === filter.name)?.type ?? "str";
    fieldOperators = getOperatorsForType(ftype);
    filter.fieldOperator = fieldOperators[0];
  };

  const handleBoolValClick = (b: boolean) => {
    filter.value = b;
  };
</script>

<div class="flex justify-start gap-2 mr-4 h-10 overflow-hidden">
  {#if filter.logicOperator !== "FIRST"}
    <IconButton disabled>{filter.logicOperator}</IconButton>
  {/if}
  <select
    title={`Select table (${filter.table})`}
    class="rounded-lg font-normal"
    bind:value={filter.table}
    onchange={handleTableChange}
  >
    {#each tableColumns as table}
      <option value={table}>
        {table}
      </option>
    {/each}
  </select>
  <select
    title={`Select field (${filter.name})`}
    class="rounded-lg font-normal"
    bind:value={filter.name}
    onchange={handleFieldChange}
  >
    {#each fieldColumns[filter.table] as { name }}
      <option value={name}>
        {name}
      </option>
    {/each}
  </select>
  <select
    title={`Select field operator`}
    class="rounded-lg font-normal"
    bind:value={filter.fieldOperator}
  >
    {#each fieldOperators as fieldOperator}
      <option value={fieldOperator}>
        {fieldOperator}
      </option>
    {/each}
  </select>
</div>
{#if ftype === "bool"}
  <Checkbox.Root
    checked={filter.value ? true : false}
    onCheckedChange={handleBoolValClick}
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
{:else}
  <input
    type="text"
    bind:value={filter.value}
    placeholder="filter value"
    class="h-10 pl-10 pr-4 rounded-lg border font-normal text-foreground placeholder-muted-foreground bg-background border-border shadow-sm"
  />
{/if}
