<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

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

  let ftype: string = $state("str");
  let fieldOperators: FieldOperator[] = $state([]);

  const syncFieldConfig = () => {
    const tableFields = fieldColumns[filter.table] ?? [];
    if (tableFields.length === 0) return;

    if (!tableFields.find((field) => field.name === filter.name)) {
      filter.name = tableFields[0].name;
    }

    ftype = tableFields.find((field) => field.name === filter.name)?.type ?? "str";
    fieldOperators = getOperatorsForType(ftype);

    if (!fieldOperators.includes(filter.fieldOperator)) {
      filter.fieldOperator = fieldOperators[0];
    }
  };

  const handleTableChange = () => {
    syncFieldConfig();
  };

  const handleFieldChange = () => {
    syncFieldConfig();
  };

  const handleBoolValClick = (b: boolean) => {
    filter.value = b;
  };

  const boolValue = $derived.by(() => filter.value === true || filter.value === "true");

  // Synchronize field/operator state from initial table selection
  syncFieldConfig();
</script>

<div class="rounded-lg border border-border/40 bg-background/70 p-2 space-y-2">
  <div class="flex flex-wrap items-center gap-2">
    {#if filter.logicOperator !== "FIRST"}
      <span class="rounded-md bg-primary/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-primary">
        {filter.logicOperator}
      </span>
    {/if}

    <select
      title={`Select table (${filter.table})`}
      class="h-8 rounded-md border border-border/60 bg-background px-2 text-xs font-medium"
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
      class="h-8 rounded-md border border-border/60 bg-background px-2 text-xs font-medium"
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
      title="Select field operator"
      class="h-8 rounded-md border border-border/60 bg-background px-2 text-xs font-medium"
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
    <div class="flex items-center gap-2">
      <span class="text-[10px] uppercase tracking-wide text-muted-foreground">Value</span>
      <button
        type="button"
        onclick={() => handleBoolValClick(true)}
        class={`h-7 rounded-md px-2 text-xs font-medium border transition-colors ${
          boolValue
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border/60 bg-background text-foreground hover:bg-accent"
        }`}
      >
        true
      </button>
      <button
        type="button"
        onclick={() => handleBoolValClick(false)}
        class={`h-7 rounded-md px-2 text-xs font-medium border transition-colors ${
          !boolValue
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border/60 bg-background text-foreground hover:bg-accent"
        }`}
      >
        false
      </button>
    </div>
  {:else}
    <input
      type={ftype === "int" || ftype === "float" ? "number" : "text"}
      bind:value={filter.value}
      placeholder="Filter value"
      class="h-8 w-full rounded-md border border-border/60 bg-background px-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
    />
  {/if}
</div>
