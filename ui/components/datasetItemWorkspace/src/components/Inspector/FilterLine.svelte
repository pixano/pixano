<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { onMount } from "svelte";

  import { IconButton } from "@pixano/core";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";

  import {
    getOperatorsForType,
    type FieldCol,
    type FieldOperator,
    type ObjectsFilter,
  } from "../../lib/types/datasetItemWorkspaceTypes";

  export let filter: ObjectsFilter;
  export let tableColumns: string[];
  export let fieldColumns: Record<string, FieldCol[]>;

  let ftype: string = "";

  onMount(() => handleTableChange());

  let fieldOperators: FieldOperator[] = [];

  const handleTableChange = () => {
    filter.name = fieldColumns[filter.table][0].name;
    handleFieldChange();
  };

  const handleFieldChange = () => {
    ftype = fieldColumns[filter.table].find((field) => field.name === filter.name)!.type;
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
    on:change={handleTableChange}
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
    on:change={handleFieldChange}
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
  <Checkbox handleClick={handleBoolValClick} checked={filter.value ? true : false} />
{:else}
  <input
    type="text"
    bind:value={filter.value}
    placeholder="filter value"
    class="h-10 pl-10 pr-4 rounded-lg border font-normal text-slate-800 placeholder-slate-500 bg-slate-50 border-slate-300 shadow-slate-300"
  />
{/if}
