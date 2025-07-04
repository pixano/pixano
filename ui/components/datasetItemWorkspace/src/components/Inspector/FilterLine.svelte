<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { onMount } from "svelte";

  import { IconButton } from "@pixano/core";

  import {
    getOperatorsForType,
    type FieldCol,
    type FieldOperator,
    type ObjectsFilter,
  } from "../../lib/types/datasetItemWorkspaceTypes";

  export let filter: ObjectsFilter;
  export let tableColumns: string[];
  export let fieldColumns: Record<string, FieldCol[]>;

  onMount(() => handleTableChange());

  let fieldOperators: FieldOperator[] = [];

  const handleTableChange = () => {
    filter.name = fieldColumns[filter.table][0].name;
    handleFieldChange();
  };

  const handleFieldChange = () => {
    const ftype = fieldColumns[filter.table].find((field) => field.name === filter.name)!.type;
    fieldOperators = getOperatorsForType(ftype);
    filter.fieldOperator = fieldOperators[0];
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
<input
  type="text"
  bind:value={filter.value}
  placeholder="filter value"
  class="h-10 pl-10 pr-4 rounded-lg border font-normal text-slate-800 placeholder-slate-500 bg-slate-50 border-slate-300 shadow-slate-300"
/>
